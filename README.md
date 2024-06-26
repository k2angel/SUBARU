# SUBARU
渋ダウンローダー.

## 使い方
### refresh tokenを持っている人用
   1. settings.tomlにrefresh tokenを書き込む
   2. ```pip install -r requirements.txt``` を実行
   3. ``main.py`` を実行
### refresh tokenを持っていない人用
   1. 自分のchromeのバージョンに合ったchromedriverをディレクトリ内に配置する
   2. ```pip install -r requirements.txt``` を実行
   3. ``main.py`` を実行
   4. 初回起動時chromeが立ち上がるのでpixivにログインする

## 機能
 - ダウンロード機能
   - イラスト単体
   - ユーザーが投稿したイラスト全て
   - ブックマークしたイラスト
   - フォローしたユーザーの新着イラスト
   - 検索したイラスト全て
 - オプション機能
   - ユーザー､ブックマーク､新着､検索で使用可能
   - ``settings.toml``で未入力の場合に使用されるデフォルトオプションを設定可能
   - オプション一覧
     - ``<bookmarks>users`` -> 特定のブックマーク数以下のイラストをダウンロードしないようにする
     - ``<page>page`` -> 何ページまで検索するか｡ 入力しなかった場合は全てのページを検索する (1ページ30イラスト)
       - ``<start_page>:<end_page>page`` -> 特定のページの間を取得する (ブックマーク､新着には使用不可)
       - ``<start_page>:page`` -> end_pageを指定しない場合は特定のページから全てのページを取得する (ブックマーク､新着には使用不可)
     - ``illust`` -> イラストのみダウンロードする
     - ``illust-not`` -> イラスト以外ダウンロードする
     - ``manga`` -> 漫画のみダウンロードする
     - ``manga-not`` -> マンガ以外ダウンロードする
     - ``ugoira`` -> うごイラのみダウンロードする
     - ``ugoira-not`` -> うごイラ以外ダウンロードする
     - ``r-18`` -> R-18作品のみダウンロードする
     - ``r-18-not`` -> 全年齢対象作品のみダウンロードする
     - ``r-18g`` -> R-18G作品のみダウンロードする
     - ``r-18g-not`` -> R-18G作品以外ダウンロードする
     - ``follow`` -> フォローユーザーの作品のみダウンロードする
     - ``follow-not`` -> フォローユーザー以外の作品のみダウンロードする
 - フォルダ分け機能
   - 特定のタグやユーザー､フォローしているユーザーのイラストをフォルダごとに分けるようにする
   - 曖昧タグ機能
     - 表記揺れタグを一つのタグとして扱うようにする
 - ブロック機能
   - 特定のタグやユーザー､AI生成のイラストをダウンロードしないようにする
 - うごイラ変換機能
   - 対応形式
     - gif
     - webp
     - apng
 - ストップ/リジューム機能
   - ダウンロード中に``Ctrl+C``でストップ
   - ``y``でリジューム
   - ``n``でキューを終了
 - キューリジューム機能
   - 途中で終了したキューを再開する
   - キューは何個でも保存可能
 - 通知機能
   - デスクトップ通知やdiscord webhookで通知を送る
   - レポート機能
     - 定期的にダウンロードの進捗を通知する
 - 自動ブックマーク機能
 - リロード
   - 設定ファイルを再読み込みする

## 追加したい機能
 - 削除機能