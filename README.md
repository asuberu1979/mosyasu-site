# 模写栖 / 焔崎エリス 統合サイト

GitHub Pages で無料公開する、模写栖と焔崎エリスの公式サイト。
トップで「模写栖(蒼)」と「焔崎エリス(紅)」の2つの入口に分かれる。
毎朝 6:17 に YouTube の最新動画を自動で取ってきて、ページを作り直す。

公開先(独自ドメインなし): `https://<GitHubのユーザー名>.github.io/<リポジトリ名>/`

## フォルダ
| 場所 | 役割 |
|---|---|
| `site.json` | **文言とリンクはここだけで直す。** 空欄(`""`)の項目はページに出ない |
| `assets/eris/` | エリスの絵を置く場所(下記) |
| `assets/logo/` | 模写栖のエンブレム・印影・アイコン |
| `assets/style.css` | 見た目 |
| `build_site.py` | ページを作るスクリプト(標準ライブラリだけ。pip 不要) |
| `data/videos.json` | YouTube の最新動画の記録(自動で書き換わる。手で触らない) |
| `.github/workflows/site.yml` | 毎朝の自動更新と公開の設定 |
| `_site/` | 作られたページ(GitHub には上げない) |

## はじめて公開する手順
1. GitHub で新しいリポジトリを作る(例: `mosyasu`)。**Public** にする(無料プランの Pages は公開リポジトリのみ)
2. このフォルダの中身を、そのリポジトリの `main` ブランチに上げる
   ```
   git init
   git add .
   git commit -m "統合サイト"
   git branch -M main
   git remote add origin https://github.com/<ユーザー名>/<リポジトリ名>.git
   git push -u origin main
   ```
3. リポジトリの **Settings → Pages → Build and deployment → Source** を **GitHub Actions** にする
4. **Actions** タブ →「サイトを公開」→ **Run workflow** で1回動かす(緑のチェックになれば公開完了)
5. `site.json` の `base_url` に公開先のURLを入れて上げ直す(SNSでリンクを貼ったときの画像に使う)

## 直し方
- 文言・リンクを変える: `site.json` を書き換えて GitHub に上げる。数分で反映される
- 手元で見た目を確認する: `python build_site.py` → `_site/index.html` をブラウザで開く
- YouTube の最新動画も取ってくる: `python build_site.py --fetch`

### エリスの絵を出す
`assets/eris/` に置くと、自動でページに出る。
- `key.png`(または `.jpg` / `.webp`): トップの紅の入口と、エリスのページの右側に出るメインの絵。縦長がおすすめ
- `gallery_01.png`、`gallery_02.png` …: エリスのページの「ギャラリー」に並ぶ
- 1枚あたり 1MB 以下が目安(サイト全体の上限は 1GB)。大きい絵は WebP に変換すると軽くなる

### 楽曲・MV を載せる
`site.json` の `eris.music` に、曲名と YouTube の動画ID(`watch?v=` の後ろの11文字)を入れる。動画IDが空なら、曲名だけ表示される。

### 最新動画が出ないとき
- Actions のログに「チャンネルIDが分かりません」と出ていたら、YouTube Studio → 設定 → チャンネル → 詳細設定 にある `UC` で始まるIDを、`site.json` の `youtube_channel_id` に入れる
- 取得に失敗した日は、前回の動画一覧のまま表示される(サイトは壊れない)

## 決まりごと(GitHub Pages の規約と、このサイトの方針)
- サイト上で決済までするネットショップにはしない(規約で不可)。販売は BOOTH・note など外部のお店へのリンクにする
- **本名・住所・電話番号は載せない。** 自分のサイトで直接販売すると特定商取引法の表示が必要になるので、販売は外部のお店に任せる
- 帳簿(LEDGER VAULT)や請求書のデータは、このリポジトリに入れない。公開リポジトリは中身を誰でも見られる
- 公開リポジトリは60日間動きがないと、毎朝の自動更新が止まる。対策として、月に1回 `data/videos.json` の記録を書き換えて動きを残している。それでも止まったら、Actions タブで再開できる
