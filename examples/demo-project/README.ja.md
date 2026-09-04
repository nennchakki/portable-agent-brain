# 架空のメモ保存先

[English](README.md) | 日本語

すべて作り物です。このフォルダには、説明とテストに使える架空のメモを一式そろえてあります。実際のプロジェクト、人物、組織、システム、障害を表すものではありません。

`sample-weather-cli` は、架空の天気データをコマンド例のために整形するプロジェクトです。プロジェクトの概要、話題、失敗から得たメモが入っています。個人データを使わずに、検索、作業に応じたメモの選択、メモ同士のリンク、重複確認を試せます。

ソフト本体のリポジトリで、次を実行します。

```sh
./brain search --library "$PWD/examples/demo-project" "cache expiry"

./brain context --library "$PWD/examples/demo-project" \
  --project sample-weather-cli \
  --task-type debugging \
  "debug stale cached output"
```

メモの保存も試す場合は、先にこの見本を一時フォルダへコピーします。リポジトリ内の見本は変更しないでください。

```sh
demo_library="$(mktemp -d)/sample-library"
cp -R examples/demo-project "$demo_library"

./brain learn-extract --library "$demo_library" \
  --project sample-weather-cli \
  --task-type debugging \
  --stdin < examples/demo-project/task-summary.json
```

同じ失敗から得たメモがすでにあるため、ツールは重複したファイルを作りません。要約が別の作業による確認を表す場合だけ、既存の確認待ちメモへ根拠を追加することがあります。まったく同じ要約を再送しても、根拠の数は増えません。

この見本を新しい自分用の保存先へ、自動で入れてはいけません。自分用の新しい保存先は、確認待ちメモも含めて0件から始めます。
