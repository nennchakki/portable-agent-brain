# データの書式定義

[English](README.md) | 日本語

Portable Agent Brainのメモは、先頭にYAMLの項目を持つMarkdownです。このフォルダのファイルは、YAMLやJSONを読み取った後のデータ形式を定義します。

- [`knowledge-node.schema.json`](knowledge-node.schema.json): バージョン1のメモの項目と、リンク関係の形。
- [`project.schema.json`](project.schema.json): `project.yaml` に書く検索の設定。
- [`task-summary.schema.json`](task-summary.schema.json): `brain learn-extract` へ渡す短い作業要約。

項目名は翻訳しません。実際のファイル名、コマンド名、JSON・YAMLの項目名は日英で共通なので、日本語の説明を読んでいても書式定義のとおりに書いてください。

読み取り機能が対応するYAMLは一部に限られます。グラフの一覧は `[]`、または2つの空白で字下げした引用符付き文字列の一覧にします。関係は、引用符で囲んだObsidianのwikilinkで書きます。

JSON Schemaだけでは、そのファイルとリポジトリ内のほかのデータとの関係を確認できません。リポジトリのvalidatorは、次の点も調べます。

- 変わらないIDとプロジェクトslugが重複していない。
- 各プロジェクトの主なメモが決められた場所にある。
- wikilinkの参照先が存在し、同じ名前の候補が複数ない。
- 関係の種類に合うメモを参照している。
- パスが保存先からの相対指定で、外へ出ない。
- 置き換え関係が相互に対応し、循環していない。
- プロジェクト設定のパスと作業の種類が正しい。
- 確認待ちメモが指定のフォルダにある。
- 実行したコマンドの範囲に応じて、秘密情報らしい内容と公開前の安全性を調べる。

`TEMPLATE.md` と `examples/` の内容は説明用です。利用者自身が保存したメモではありません。

`brain validate` が調べるのは、保存先の書式と、一般的な秘密情報らしい文字列です。公開して安全だという保証にはなりません。公開版では、`brain release-check`、必要に応じた外部denylist、人による確認も行ってください。
