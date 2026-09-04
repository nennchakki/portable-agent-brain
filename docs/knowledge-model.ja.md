# メモの書式と検索時の優先順

[English](knowledge-model.md) | 日本語 | [説明書一覧](README.ja.md)

Portable Agent Brainでは、だれでも使えるソフトと、利用者ごとのデータを分けます。

```text
公開ソフト                           非公開のメモ保存先
brain CLI ------------------------> Markdown + YAML
schemasと検査機能 ----------------> プロジェクトのメモ
AI接続用の指示書 -----------------> 発見したことや判断
書式見本 -------------------------> 確認待ちのメモ
```

自分が書いたMarkdownが、メモの原本です。検索結果、AIに渡す抜粋、HTML表示、リンクの図は、原本から作る見え方の違う表示であり、代わりの保存先ではありません。

## 保存先のフォルダ構成

`brain init` は次のフォルダを作ります。READMEと書式見本は、必要なものだけコピーできるよう、公開ソフト側に残します。

```text
agent-library/
├── README.md
├── principles/
├── protocols/
├── projects/
│   └── <slug>/
│       ├── <slug>.md
│       └── project.yaml
├── lessons/
├── decisions/
├── preferences/
├── procedures/
├── concepts/
├── references/
├── profiles/
├── skills/
└── inbox/
    └── candidates/
```

空のフォルダには `.gitkeep` がある場合があります。`TEMPLATE.md` は書き方の説明で、保存済みのメモではありません。

## Markdownでメモを書く

各メモは、先頭にYAMLの項目を持つMarkdownファイルです。この先頭部分をfrontmatterと呼びます。メモとそのリンクが、グラフの1つの項目になります。次は、読み取り機能が受け付ける項目を示す架空の例です。

```yaml
---
graph_version: 1
id: lesson:sample-weather-cli/cache-expiry
type: lesson
project_id: sample-weather-cli
status: active
authority: verified
confidence: high
source_type: demo-fixture
created: 2026-01-01
project:
  - "[[projects/sample-weather-cli/sample-weather-cli|Sample Weather CLI]]"
domains:
  - "[[concepts/cache-expiry|Cache Expiry]]"
related: []
---
```

ファイルを移動しても変わらない `namespace:key` 形式のIDを付けます。プロジェクトのslugには小文字を使います。グラフの項目は最上位に置き、関係の一覧は2つの空白で字下げした、引用符付きのwikilinkにします。空の一覧は `[]` と書きます。

この版の読み取り機能は、YAMLの機能を一部に限定しています。YAML anchor、グラフ項目を入れ子にしたmap、空でないinline list、複数行のgraph scalarは使いません。種類ごとの詳しい説明はMarkdown本文に書きます。

## メモの種類

対応する主な種類は次のとおりです。

- `project-knowledge` と `project-rule`
- `principle` と `protocol`
- `lesson` と `decision`
- `fact`、`preference`、`constraint`、`procedure`
- `concept`、`reference`、`profile`、`skill`

種類は、そのメモを何に使うかを表します。種類だけで内容が確認済みになったり、ほかの資料より優先されたりはしません。

## プロジェクトごとに概要メモを1つ置く

各プロジェクトの主な概要メモは `projects/<slug>/<slug>.md` の1つだけです。このメモに `node_role: project` と、変わらないプロジェクトIDを付けます。同じ概要のコピーを複数作らないでください。

隣の `project.yaml` で、検索や選択の方法を指定します。

```yaml
schema_version: 1
slug: sample-weather-cli
node: projects/sample-weather-cli/sample-weather-cli.md
project_type: software
domains:
  - command-line-tools
status: active
always_include: []
task_include:
  debugging:
    - lessons/sample-weather-cli/cache-expiry.md
search_include:
  - projects/sample-weather-cli/
  - lessons/sample-weather-cli/
```

- `node` は、プロジェクトの主なMarkdownを指します。
- `always_include` には、そのプロジェクトのすべての作業で確認するメモだけを指定します。
- `task_include` は、作業の種類と、そのとき確認するメモを対応させます。
- `search_include` は現在、情報として読み取るだけで、検索範囲を制限しません。除外やプライバシー保護には使えません。
- `domains` は検索語の手がかりです。内容が確認済みかどうかは表しません。

未対応の作業種類、存在しないパス、プロジェクトslugの不一致は検査エラーになります。同じ参照を繰り返し書いた場合、メモを選ぶときに重複を除きます。validatorは重複自体をエラーにはしません。

## メモ同士の関係

リンクには種類と向きがあります。使える項目名は次のとおりです。

| 項目 | 表す関係 |
|---|---|
| `project` | このメモが属するプロジェクトの概要メモ。 |
| `domains` | このメモが扱う、既存の話題メモ。 |
| `related` | 内容に関係がある別のメモ。 |
| `uses` | プロジェクトや手順が使う資料。 |
| `depends_on` | 明示された前提条件。 |
| `implements` | 作業上の決まり、手順、判断が実現するもの。 |
| `prevents` | 作業上の決まりや手順が防ぐ失敗。 |
| `caused_by` | 失敗から得たメモと、確認できた原因。 |
| `conflicts_with` | 未確認の観察と、食い違う可能性がある判断。 |
| `supersedes` | 新しいメモから、それが置き換える古いメモ。 |
| `superseded_by` | 古いメモから、それを置き換えた新しいメモ。 |

リンクは、読者や検索機能が関係するメモを見つけるために使います。リンクしただけで、内容が正しいと証明されたり、ほかのプロジェクトにも適用されたり、確認済みになったりはしません。wikilinkにはメモ保存先からの相対パスを使い、絶対パスや `..` を入れないでください。

## 内容が食い違う場合の優先順

`authority` は、情報が食い違うときの扱いを表します。`status` や保存場所とは別の項目です。次の順で確認します。

1. メモの外にある、現在のプロジェクト資料。内容が変わっていれば、これを優先します。
2. `canonical`。人が確認し、現在使用しているプロジェクト資料、判断、指示。
3. `verified`。根拠と照らし合わせて確認したメモ。
4. `observed`。観察したが、十分に確認できていない内容。
5. `candidate`。人の確認を待っているメモ。
6. `rejected` と `superseded`。通常の作業を導く情報としては使いません。

検索結果にはID、元のパス、`authority`、`status`、選ばれた理由を残します。AIが、確認待ちのメモと、現在使っている判断を区別できるようにします。

## 新しいメモは人が確認する

`inbox/candidates/` には、確認待ちのメモを置きます。ここにあるだけでは、AIが従う指示になりません。`candidate: true`、`review_status: pending`、`status: pending`、`authority: candidate` を持ちます。検索結果に警告付きで出ることはありますが、内容が食い違う場合は、確認済みの指示や判断を優先します。

人は、メモを却下する、未確認の観察として残す、既存メモの根拠に加える、今後使う内容として確認する、のいずれかを選べます。ツールが自動で決めることはありません。

## Obsidianで開く

メモの保存先全体をObsidianの保管庫として開きます。Markdown、frontmatter、wikilinkを見るために追加プラグインは不要です。個人の `.obsidian/` 設定は画面表示の設定で、メモの書式を決めるものではありません。

Obsidianのグラフには、検査対象外の書式見本や補助ファイルも表示される場合があります。どのメモが通常のグラフに入ったかは、validatorの件数で確認します。画面の図では、それより多く見えることがあります。

必要なら、HTMLの表示も生成できます。ただし、元になる記録はMarkdownのままです。

## 書式定義と検査

機械が読む書式の定義は [`schemas/`](../schemas/README.ja.md) にあります。validatorは、IDの重複、関係一覧の書式違反、存在しないリンクや同じ名前で区別できないリンク、不正なプロジェクト設定、置き換え関係の循環、安全でないパスなどをエラーにします。リンクのないメモには警告できますが、内容を推測してリンクを作ることはありません。
