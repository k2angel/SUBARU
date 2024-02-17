# SUBARU
pixiv downloader.

## How to Use
1. login_run.batを起動
2. pixivにログインしたらコンソール画面にrefresh_tokenが表示されるのでコピー
3. settings.tomlに貼り付ける ```refresh_token = ["<REFRESH_TOKEN>""]```

## Features
 - ダウンロード機能
   - イラスト単体
   - ユーザーが投稿したイラスト全て
   - ブックマークしたイラスト
   - フォローしたユーザーの新着イラスト
   - 検索したイラスト全て
 - ブロック機能
   - 特定のタグやユーザーのイラストをダウンロードしないように
   - settings.tomlにタグ名やユーザーidを書き込む ```[ignore] -> tag = ["<TAG_NAME>"], user = ["<USER_ID>"]```
 - フォルダ分け機能
   - 特定のタグを持つイラストをフォルダごとに分ける
   - settings.tomlにタグ名を書き込む ```[folder] -> tag = ["<TAG_NAME>"]```
 - うごイラ変換機能
   - うごイラをgifに変換
   - webpやmp4は非対応
 - 通知機能
   - デスクトップ通知やdiscord webhookで通知を送る
   - settings.tomlから設定を行う
 - OffsetLimitBypass
   - offsetが5000を超えるとこれ以上取得できなくなるがこれを回避する