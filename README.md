# SUBARU
渋ダウンローダー.

## 使い方
1. ```pip install -r requirements.txt``` を実行
2. ``main.py`` を実行
3. 初回起動時はchromeが起動するのでpixivにログインする

## 機能
 - ダウンロード機能
   - イラスト単体
   - ユーザーが投稿したイラスト全て
   - ブックマークしたイラスト
   - フォローしたユーザーの新着イラスト
   - 検索したイラスト全て
 - オプション機能
   - ``<bookmarks>users`` -> 特定のブックマーク数以下のイラストをダウンロードしないようにする
   - ``<page>page`` -> 何ページまで検索するか｡ 入力しなかった場合は全てのページを検索する (1ページ30イラスト)
     - ``<start_page>:<end_page>page`` -> 特定のページの間を取得する
     - ``<start_page>:page`` -> end_pageを指定しない場合は特定のページから全てのページを取得する
   - ``ugoira`` -> うごイラのみをダウンロードする
   - ``ugoira-not`` -> うごイラ以外をダウンロードする
 - ブロック機能
   - 特定のタグやユーザーのイラストをダウンロードしないようにする
   - settings.tomlにタグ名やユーザーidを書き込む ```[ignore] -> tag = ["<TAG_NAME>"], user = ["<USER_ID>"]```
 - フォルダ分け機能
   - 特定のタグを持つイラストをフォルダごとに分けるようにする
   - settings.tomlにタグ名を書き込む ```[folder] -> tag = ["<TAG_NAME>"]```
 - うごイラ変換機能
   - settings.tomlにフォーマット名を書き込む ```[ugoira2gif] -> format = "<FORMAT>"```
   - 対応形式
     - gif
     - webp
 - 通知機能
   - デスクトップ通知やdiscord webhookで通知を送る
   - settings.tomlから設定を行う
 - リロード
   - 設定ファイルを再読み込みする
 - OffsetLimitBypass
   - offsetの上限をバイパスする

## 追加したい機能
 - 特に無し