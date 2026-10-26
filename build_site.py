# 模写栖 / 焔崎エリス 統合サイトの生成スクリプト
#
#   python build_site.py           -> site.json と data/videos.json から _site/ にページを作る
#   python build_site.py --fetch   -> 先に YouTube の最新動画を取ってから作る(GitHub Actions が毎朝これを実行)
#
# 文言・リンクは site.json、エリスの絵は assets/eris/ に置く。HTML を直接書き換える必要はない。
# 外部ライブラリは使わない(Python 3.9 以上の標準ライブラリだけ)。
import html
import json
import re
import shutil
import sys
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUT = ROOT / '_site'
DATA = ROOT / 'data' / 'videos.json'
JST = timezone(timedelta(hours=9))
UA = {'User-Agent': 'Mozilla/5.0 (mosyasu-site builder)', 'Accept-Language': 'ja,en;q=0.8'}


def esc(s):
    return html.escape(str(s or ''), quote=True)


def load_config():
    with open(ROOT / 'site.json', encoding='utf-8') as f:
        return json.load(f)


# ── YouTube の最新動画(RSS。APIキー不要) ─────────────────
def http_get(url, timeout=20):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode('utf-8', 'replace')


def resolve_channel_id(handle):
    """@ハンドルのページから UC で始まるチャンネルIDを探す。取れなければ None"""
    page = http_get(f'https://www.youtube.com/@{handle}')
    for pat in (r'<link rel="canonical" href="https://www\.youtube\.com/channel/(UC[\w-]{22})"',
                r'"externalId":"(UC[\w-]{22})"', r'"channelId":"(UC[\w-]{22})"'):
        m = re.search(pat, page)
        if m:
            return m.group(1)
    return None


def fetch_feed(channel_id, limit):
    ns = {'a': 'http://www.w3.org/2005/Atom', 'yt': 'http://www.youtube.com/xml/schemas/2015',
          'media': 'http://search.yahoo.com/mrss/'}
    root = ET.fromstring(http_get(f'https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}'))
    out = []
    for e in root.findall('a:entry', ns):
        vid = e.findtext('yt:videoId', default='', namespaces=ns)
        link = e.find('a:link', ns)
        href = link.get('href') if link is not None else f'https://www.youtube.com/watch?v={vid}'
        out.append({
            'id': vid,
            'title': e.findtext('a:title', default='', namespaces=ns),
            'published': e.findtext('a:published', default='', namespaces=ns)[:10],
            'url': href,
            'short': '/shorts/' in href,
        })
    return out[:limit]


def fetch_all(cfg):
    """取れたチャンネルだけ上書きする。失敗したら前回のデータを残す"""
    data = {}
    if DATA.exists():
        data = json.loads(DATA.read_text(encoding='utf-8'))
    changed = False
    for key in ('mosyasu', 'eris'):
        sec = cfg[key]
        limit = int(cfg.get('videos', {}).get(f'count_{key}', 6))
        try:
            cid = sec.get('youtube_channel_id') or data.get(key, {}).get('channel_id')
            if not cid and sec.get('youtube_handle'):
                cid = resolve_channel_id(sec['youtube_handle'])
            if not cid:
                print(f'[{key}] チャンネルIDが分かりません。site.json の youtube_channel_id に UC... を入れてください')
                continue
            videos = fetch_feed(cid, limit)
            new = {'channel_id': cid, 'videos': videos}
            if data.get(key) != new:
                data[key] = new
                changed = True
            print(f'[{key}] {len(videos)}本 取得')
        except Exception as ex:  # ネットワーク・形式の失敗は前回分で続行
            print(f'[{key}] 取得に失敗({ex.__class__.__name__}: {ex})。前回のデータを使います')
    # 公開リポジトリは60日動きがないと定時処理が止まるので、月に1回だけ記録を変えて動きを残す
    month = datetime.now(JST).strftime('%Y-%m')
    if data.get('heartbeat') != month:
        data['heartbeat'] = month
        changed = True
    if changed:
        DATA.parent.mkdir(parents=True, exist_ok=True)
        DATA.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding='utf-8')
    return data


# ── 部品 ─────────────────────────────────────────
def head(cfg, title, desc, page, accent, og_image='assets/logo/icon-512.png'):
    base = cfg['site'].get('base_url', '').rstrip('/')
    og_img = f'{base}/{og_image}' if base else og_image
    canonical = f'<link rel="canonical" href="{esc(base)}/{page}">' if base else ''
    return f'''<!doctype html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<title>{esc(title)}</title>
<meta name="description" content="{esc(desc)}">
<meta name="theme-color" content="#060A18">
<meta property="og:type" content="website">
<meta property="og:title" content="{esc(title)}">
<meta property="og:description" content="{esc(desc)}">
<meta property="og:image" content="{esc(og_img)}">
<meta name="twitter:card" content="{'summary_large_image' if 'eris/' in og_image else 'summary'}">
{canonical}
<link rel="icon" href="assets/logo/emblem_on_dark.svg" type="image/svg+xml">
<link rel="apple-touch-icon" href="assets/logo/apple-touch-icon.png">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Shippori+Mincho:wght@600;800&family=Zen+Kaku+Gothic+New:wght@400;700&family=JetBrains+Mono:wght@400;600&display=swap">
<link rel="stylesheet" href="assets/style.css">
</head>
<body class="{accent}">
'''


def nav(cfg, current):
    m, e = cfg['mosyasu'], cfg['eris']
    item = lambda href, label, key, cls: f'<a href="{href}" class="{cls}{" is-current" if current == key else ""}"{" aria-current=page" if current == key else ""}>{esc(label)}</a>'
    return f'''<header class="topbar">
  <a href="index.html" class="brand" aria-label="トップへ"><img src="assets/logo/emblem_on_dark.svg" alt="" width="28" height="28"><span>{esc(m["name"])}</span></a>
  <nav class="topnav" aria-label="サイト内">
    {item("mosyasu.html", m["name"], "mosyasu", "to-blue")}
    {item("eris.html", e["name"], "eris", "to-red")}
  </nav>
</header>
'''


def footer(cfg):
    year = datetime.now(JST).year
    return f'''<footer class="foot">
  <img src="assets/logo/seal_on_dark_red.svg" alt="模写栖の印" width="44" height="44" class="foot-seal">
  <div>© {year} {esc(cfg["mosyasu"]["name"])} ({esc(cfg["mosyasu"]["roman"])})</div>
  <div class="foot-sub">焔崎エリス / Homurasaki Eris は {esc(cfg["mosyasu"]["name"])} のオリジナルキャラクターです。</div>
</footer>
</body>
</html>
'''


def link_list(links):
    items = [(k, v) for k, v in links.items() if v]
    if not items:
        return ''
    return '<ul class="links">' + ''.join(
        f'<li><a href="{esc(v)}" target="_blank" rel="noopener">{esc(k)}<span aria-hidden="true">↗</span></a></li>' for k, v in items) + '</ul>'


def video_grid(videos, channel_url, empty_label):
    if not videos:
        return f'<p class="empty">最新の動画は <a href="{esc(channel_url)}" target="_blank" rel="noopener">{esc(empty_label)}</a> でご覧ください。</p>'
    cards = []
    for v in videos:
        thumb = f'https://i.ytimg.com/vi/{esc(v["id"])}/hqdefault.jpg'
        kind = 'Short' if v.get('short') else '動画'
        date = v.get('published', '').replace('-', '.')
        cards.append(f'''<a class="vcard" href="{esc(v["url"])}" target="_blank" rel="noopener">
  <span class="vthumb"><img src="{thumb}" alt="" loading="lazy" width="480" height="360"><span class="vkind">{kind}</span></span>
  <span class="vtitle">{esc(v["title"])}</span>
  <span class="vdate">{esc(date)}</span>
</a>''')
    return '<div class="vgrid">' + '\n'.join(cards) + '</div>'


def find_image(folder, stem):
    for ext in ('webp', 'png', 'jpg', 'jpeg'):
        p = ROOT / 'assets' / folder / f'{stem}.{ext}'
        if p.exists():
            return f'assets/{folder}/{stem}.{ext}'
    return None


# ── ページ ───────────────────────────────────────
def page_index(cfg):
    m, e = cfg['mosyasu'], cfg['eris']
    eris_img = find_image('eris', 'key')
    eris_visual = f'<img class="gate-art" src="{eris_img}" alt="{esc(e["name"])}">' if eris_img else ''
    return head(cfg, cfg['site']['title'], cfg['site']['description'], '', 'is-index', eris_img or 'assets/logo/icon-512.png') + f'''<main class="gate">
  <a class="gate-half gate-blue" href="mosyasu.html">
    <img class="gate-emblem" src="assets/logo/emblem_on_dark.svg" alt="" width="120" height="120">
    <span class="gate-roman">{esc(m["roman"])}</span>
    <span class="gate-name">{esc(m["name"])}</span>
    <span class="gate-catch">{esc(m["catch"])}</span>
    <span class="gate-enter">工房に入る →</span>
  </a>
  <a class="gate-half gate-red" href="eris.html">
    {eris_visual}
    <span class="gate-roman">{esc(e["roman"])}</span>
    <span class="gate-name">{esc(e["name"])}</span>
    <span class="gate-catch">{esc(e["catch"])}</span>
    <span class="gate-enter">炎のほうへ →</span>
  </a>
  <div class="gate-seam" aria-hidden="true"></div>
</main>
''' + footer(cfg)


def page_mosyasu(cfg, data):
    m = cfg['mosyasu']
    services = ''.join(f'''<article class="svc">
  <h3>{esc(s["title"])}</h3>
  <p>{esc(s["body"])}</p>
  <ul class="tags">{"".join(f"<li>{esc(t)}</li>" for t in s.get("tags", []))}</ul>
</article>''' for s in m.get('services', []))
    flow = ''.join(f'<li><span class="step-n">{i}</span>{esc(s)}</li>' for i, s in enumerate(m.get('flow', []), 1))
    c = m.get('contact', {})
    contact = []
    if c.get('x_dm'):
        contact.append(f'<a class="btn btn-blue" href="{esc(c["x_dm"])}" target="_blank" rel="noopener">X のDMで相談する</a>')
    if c.get('form'):
        contact.append(f'<a class="btn" href="{esc(c["form"])}" target="_blank" rel="noopener">相談フォーム</a>')
    if c.get('email'):
        contact.append(f'<span class="mail">メール: <span class="mono">{esc(c["email"])}</span></span>')
    vids = data.get('mosyasu', {}).get('videos', [])
    return head(cfg, f'{m["name"]} | {m["catch"]}', m['lead'], 'mosyasu.html', 'is-blue') + nav(cfg, 'mosyasu') + f'''<main>
  <section class="hero hero-blue">
    <div class="hero-text">
      <p class="eyebrow">{esc(m["roman"])}</p>
      <h1>{esc(m["name"])}</h1>
      <p class="catch">{esc(m["catch"])}</p>
      <p class="lead">{esc(m["lead"])}</p>
    </div>
    <img class="hero-emblem" src="assets/logo/emblem_on_dark.svg" alt="模写栖のエンブレム" width="220" height="220">
  </section>

  <section class="block" id="services">
    <h2>できること</h2>
    <div class="svc-grid">{services}</div>
    {f'<p class="note">{esc(m["price_note"])}</p>' if m.get("price_note") else ''}
  </section>

  <section class="block" id="works">
    <h2>最新の動画</h2>
    {video_grid(vids, m["links"].get("YouTube", ""), "YouTube の模写栖チャンネル")}
  </section>

  <section class="block" id="flow">
    <h2>ご依頼の流れ</h2>
    <ol class="flow">{flow}</ol>
    <div class="contact">{"".join(contact)}</div>
  </section>

  <section class="block" id="links">
    <h2>リンク</h2>
    {link_list(m.get("links", {}))}
  </section>
</main>
''' + footer(cfg)


def page_eris(cfg, data):
    e = cfg['eris']
    img = find_image('eris', 'key')
    visual = f'<img class="hero-bg" src="{img}" alt="{esc(e["name"])}">' if img else '<div class="hero-flame" aria-hidden="true">焔</div>'
    hero_cls = 'hero hero-red hero-banner' if img else 'hero hero-red'
    prof = ''.join(f'<div><dt>{esc(k)}</dt><dd>{esc(v)}</dd></div>' for k, v in e.get('profile', []) if v)
    music = []
    for s in e.get('music', []):
        if s.get('youtube_id'):
            music.append(f'''<a class="track" href="https://www.youtube.com/watch?v={esc(s["youtube_id"])}" target="_blank" rel="noopener">
  <img src="https://i.ytimg.com/vi/{esc(s["youtube_id"])}/hqdefault.jpg" alt="" loading="lazy" width="480" height="360">
  <span><b>{esc(s["title"])}</b><small>{esc(s.get("note", ""))}</small></span></a>''')
        else:
            music.append(f'<div class="track track-plain"><span><b>{esc(s["title"])}</b><small>{esc(s.get("note", ""))}</small></span></div>')
    vids = data.get('eris', {}).get('videos', [])
    gallery = sorted(p.name for p in (ROOT / 'assets' / 'eris').glob('gallery_*') if p.suffix.lower() in ('.png', '.jpg', '.jpeg', '.webp'))
    gallery_html = ''
    if gallery:
        gallery_html = '<section class="block" id="gallery"><h2>ギャラリー</h2><div class="gallery">' + ''.join(
            f'<a href="assets/eris/{esc(g)}" target="_blank" rel="noopener"><img src="assets/eris/{esc(g)}" alt="{esc(e["name"])}" loading="lazy"></a>' for g in gallery) + '</div></section>'
    return head(cfg, f'{e["name"]} | {e["roman"]}', e['lead'], 'eris.html', 'is-red', img or 'assets/logo/icon-512.png') + nav(cfg, 'eris') + f'''<main>
  <section class="{hero_cls}">
    <div class="hero-text">
      <p class="eyebrow">{esc(e["roman"])}</p>
      <h1>{esc(e["name"])}</h1>
      <p class="catch">{esc(e["catch"])}</p>
      <p class="lead">{esc(e["lead"])}</p>
    </div>
    {visual}
  </section>

  {f'<section class="block" id="profile"><h2>プロフィール</h2><dl class="prof">{prof}</dl></section>' if prof else ''}

  <section class="block" id="latest">
    <h2>最新の動画</h2>
    {video_grid(vids, e["links"].get("YouTube", ""), "YouTube の焔崎エリスチャンネル")}
  </section>

  {f'<section class="block" id="music"><h2>楽曲</h2><div class="tracks">{"".join(music)}</div></section>' if music else ''}

  {gallery_html}

  <section class="block" id="links">
    <h2>リンク</h2>
    {link_list(e.get("links", {}))}
  </section>
</main>
''' + footer(cfg)


def build(fetch=False):
    cfg = load_config()
    data = fetch_all(cfg) if fetch else (json.loads(DATA.read_text(encoding='utf-8')) if DATA.exists() else {})
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir()
    shutil.copytree(ROOT / 'assets', OUT / 'assets')
    pages = {'index.html': page_index(cfg), 'mosyasu.html': page_mosyasu(cfg, data), 'eris.html': page_eris(cfg, data),
             '404.html': page_index(cfg)}
    for name, text in pages.items():
        (OUT / name).write_text(text, encoding='utf-8')
    (OUT / '.nojekyll').write_text('', encoding='utf-8')
    print('作成:', ', '.join(pages), '->', OUT)


if __name__ == '__main__':
    build(fetch='--fetch' in sys.argv)
