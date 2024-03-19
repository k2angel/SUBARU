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
   - 特定のタグやユーザー､AI生成のイラストをダウンロードしないようにする
   - settings.tomlにタグ名かユーザーIDを書き込む ```[ignore] -> tag = ["<TAG_NAME>"], user = [<USER_ID>]```
   - settings.tomlでAI生成のイラストをダウンロードしないようにするか切り替える ```[ignore] -> ai_illust = true```
 - フォルダ分け機能
   - 特定のタグやユーザーのイラストをフォルダごとに分けるようにする
   - settings.tomlにタグ名かユーザーIDを書き込む ```[folder] -> tag = ["<TAG_NAME>"], user = [<USER_ID>]```
   - 曖昧タグ機能
     - 同じ意味合いの別名のタグを同じタグとして扱うようにする
     - settings.tomlにタグ名を書き込む ```[folder] -> vague = [{tag = "<TAG_NAME>", vague = ["<VAGUE_TAG_NANE>",...]}]``` - 例 ![](https://cdn.discordapp.com/attachments/1111172092654796813/1218064910009765918/image.png?ex=66064e59&is=65f3d959&hm=feb72dc0b9cda560c89b24fa0c25ad02ca55c10e0263ebe7d6b08b121d40c3fb&)
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