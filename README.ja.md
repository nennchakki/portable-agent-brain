# Portable Agent Brain

[English](README.md) | 日本語

> 使うAgentが変わっても、知識は手元に。

Portable Agent Brainは、AIコーディングAgentと共有する知識を、手元のMarkdownファイルに保存するツールです。プロジェクトの決定事項、作業から得た教訓、手順、利用者の好みを残し、次のタスクで必要なものだけを取り出します。

公開リポジトリに含まれるのは、CLI、スキーマ、Agentとの接続設定、テンプレート、ドキュメントです。利用者の知識や会話履歴は含みません。

初めて使う方は「まず空のLibraryを作る」から読み進めてください。それ以降は、保存する知識の扱いやAgentとの接続を確認したいときに参照できます。

## Agentを替えても、知識を引き継ぐ

Agent内蔵のメモリは便利ですが、製品やアカウントに結び付くことがあります。Portable Agent Brainでは、保存した知識の正本をAgentの外に置きます。

```text
Claude Code ─┐
Codex ───────┼─> 必要な知識だけを取得 ─> 利用者が管理するLibrary
その他のAgent ┘
```

Libraryは、知識メモをまとめた通常のディレクトリです。MarkdownとYAMLを直接読んで編集でき、Gitで履歴を管理したり、Obsidianのvaultとして開いたりできます。Obsidianは必須ではありません。

Agentの計画立案、ツール実行、権限管理、モデル選択は、使っているAgentが担います。このツールが提供するのは、Agent間で共有できる知識の保存・検索機能です。

## できること

- `brain`コマンドによる初期設定、検索、知識候補の保存。
- タスクの種類とプロジェクトに応じた検索、文字数を制限したcontextの作成。
- Markdownの知識メモを、型付きの`[[wikilink]]`で結ぶKnowledge Graph。
- secret検査、重複抑制、独立した裏付けの追加、矛盾の警告。
- Claude Code、Codex、`AGENTS.md`を使うAgentとの接続。
- テンプレートとスキーマの検証、公開前の安全性チェック。
- ローカルだけでの運用。必要な場合に限り、private Git remoteを追加。

ベクトルDB、埋め込みモデル、ホスティングサービスは不要です。実行時に外部のPythonパッケージも必要ありません。

## まず空のLibraryを作る

macOSまたはLinuxと、Python 3.11以降が必要です。リポジトリのcloneにはGitを使いますが、Libraryの運用にGitは必須ではありません。

```sh
git clone https://github.com/nennchakki/portable-agent-brain.git
cd portable-agent-brain
./brain setup
```

セットアップでは、Libraryの保存先、接続するAgent、`brain`コマンドの設置、Gitの利用方法を選びます。既存のAgent設定では、関係のない部分を保持して必要な設定だけを加えます。

対話式セットアップを使わず、空のLibraryだけを作る場合は、保存先を明示します。

```sh
export BRAIN_LIBRARY="${HOME}/agent-library"
./brain init --library "$BRAIN_LIBRARY"
```

保存先の優先順位は、コマンドの`--library`、環境変数`BRAIN_LIBRARY`、セットアップで保存した既定値、標準の`~/agent-library`の順です。ホームディレクトリ以外の場所も選べます。

`init`は空のフォルダを作成します。サンプルやテンプレートを利用者の知識として自動登録することはありません。

## プロジェクトを登録して、必要な知識を取り出す

プロジェクトを登録するには、`templates/project/`を参考に、Library内へプロジェクトのMarkdownと`project.yaml`を置きます。プレースホルダーを実際の内容に置き換えてから使ってください。[導入手順](docs/getting-started.md)に登録方法を記載しています。

以下は、架空の`sample-weather-cli`プロジェクトを登録した場合の例です。

```sh
./brain search --library "$BRAIN_LIBRARY" "cache expiry"
./brain context --library "$BRAIN_LIBRARY" \
  --project sample-weather-cli \
  "debug stale cached output"
```

`search`は一致する知識を探すコマンドです。`context`は、プロジェクトの方針やタスクの種類に応じて、Agentへ渡す知識を絞り込みます。Library全体をAgentの指示へ詰め込む使い方はしません。

明らかな誤字修正など、過去の知識が判断を変えないタスクでは、検索を省略できます。

## タスクの終了時に、再利用できる知識だけを残す

意味のある作業を終えて結果を検証したら、Agentまたは利用者が短いJSON要約を用意します。`learn-extract`はその要約を検査し、再利用できる内容をレビュー待ちの候補として保存します。

```sh
./brain learn-extract --library "$BRAIN_LIBRARY" \
  --project sample-weather-cli \
  --task-type debugging \
  --stdin < examples/demo-project/task-summary.json
```

この例のJSONは完全に架空のものです。実際の作業では、[要約テンプレート](templates/task-summary.json)に沿って、検証した発見や再利用できる手順だけを渡してください。会話全文やツールの出力ログを渡してはいけません。

新しい知識がない場合は、何も保存しません。保存する場合も、書き込み先は`inbox/candidates/`だけです。

## 過去の会話履歴を自動で採掘する機能は未実装

v0.1.0の`setup --history-source`は、指定したパスが存在するかを確認し、履歴を安全に確認するための手順を表示します。履歴ファイルの中身は読みません。過去の会話を解析して知識を抽出したり、候補を一括登録したりする処理もありません。

これは履歴処理部分の制限です。Libraryの作成やAgentとの接続など、通常のセットアップ処理は実行されます。`--history-source`を付けても、セットアップ全体が確認だけで終わるわけではありません。

現在動く`learn-extract`が受け取るのは、Agentや利用者がすでに整理したJSON要約です。タスク終了時の要約から候補を保存する機能と、蓄積された会話履歴から要約そのものを作る機能は別です。

履歴の自動読込・解析・抽出は今後の実装対象です。詳しい境界は[プライバシーと履歴の扱い](docs/privacy.md)を参照してください。

## 公開Engineと利用者の知識を分ける

```text
portable-agent-brain/        公開Engineのリポジトリ
  brain
  tools/
  adapters/
  schemas/
  templates/
  examples/                 架空のサンプルだけ

agent-library/              利用者が管理する非公開Library
  projects/
  lessons/
  decisions/
  preferences/
  procedures/
  concepts/
  inbox/candidates/
```

実際の知識は、公開Engineとは別の場所に保存してください。両者を分けておけば、Engineを更新するときに、利用者の知識やそのGit履歴を公開リポジトリへ混ぜずに済みます。

## 候補は人間がレビューする

知識は次の流れで扱います。

```text
タスク
  → 必要な知識を取得
  → 作業を完了し、結果を検証
  → 再利用できる内容があるか判断
  → 短いJSON要約を検査
  → レビュー待ちの候補を保存
  → 次のタスクで、候補であることを警告して取得
  → 人間がレビュー
```

判断の根拠として優先するのは、現在のプロジェクトのソース、有効なRule・Decision、検証済みの知識、観測段階の知識、レビュー待ちの候補の順です。候補が既存の方針を上書きすることはありません。

同じ内容の重複を抑え、別のタスクで得た裏付けを加える仕組みはあります。矛盾を検出した場合は警告しますが、自動で統合したり、既存の決定を置き換えたりはしません。恒久的なRuleやSkillへの昇格も、人間の判断に残します。

判定の詳細は[Knowledgeモデル](docs/knowledge-model.md)と[自動capture](docs/automatic-capture.md)に記載しています。

## Agentとの接続方法

| 対象 | 接続方法 |
|---|---|
| Claude Code | ユーザー設定から共通アダプターを読み込む短いimport。 |
| Codex | 適切なグローバル`AGENTS.md`への管理ブロック追加。 |
| Generic `AGENTS.md` Agent | 同じアダプターを参照する管理ブロック。 |
| その他のAgent | 製品に依存しない、初回接続用プロンプト。 |

アダプターは、いつ知識を検索し、いつ候補を保存するかをAgentへ伝える短い指示です。Libraryの内容を丸ごとコピーするものではありません。繰り返しセットアップしても、同じ管理ブロックを重複追加しません。

個別の設定先と注意点は[Agent連携](docs/agent-integration.md)、未対応Agentへの接続指示は[汎用プロンプト](prompts/connect-agent.md)を参照してください。

## 知識はローカル保存、Git remoteは任意

標準ではローカルだけで動作します。バックアップや複数端末の同期が必要な場合に、Library専用のprivate Git remoteを設定してください。初回push前には、remoteが非公開であることと、送信するファイルに秘密情報がないことを確認します。

公開配布物には、個人の知識、会話履歴、candidate、runtime metrics、認証情報を含めません。候補の保存時にはsecretらしい入力を拒否します。ただし、パターン検査であらゆる機密情報を見分けられるわけではありません。

ローカル保存でも、検索した文章をAgentへ渡せば、そのAgentの提供元が内容を処理する場合があります。利用するAgentのデータ設定を確認し、渡す情報は必要な範囲に絞ってください。

## Sandboxや読み取り専用のLibraryで使う

Libraryの保存先には、ホストのディレクトリだけでなく、`/brain`や`/workspace/.brain`などのマウント先も指定できます。Agentの実行環境から見えるパスを使ってください。

検索は読み取り専用のLibraryでも動作します。候補を保存したい場合は、`inbox/candidates/`だけを書き込み可能にする構成も使えます。[Sandboxでの設定](docs/sandbox.md)を参照してください。

## 公開する前に検査する

Engineを変更して公開する前に、次のコマンドを実行します。

```sh
./brain release-check
```

secret、非公開のパス、実際のcandidateやLibraryデータ、バックアップ、Git履歴、リンク切れなどを検査します。個人名や実プロジェクト名の検査には、公開リポジトリの外に置いたJSON配列を`--denylist`で指定してください。指定しない場合、個人固有の語は検査対象に入りません。

検査対象と限界、配布アーカイブの扱いは[公開前の安全性チェック](docs/privacy.md)にまとめています。

## 詳しい説明と問い合わせ先

以下の詳細ドキュメントは英語です。

- [導入手順](docs/getting-started.md)
- [Agentとの連携](docs/agent-integration.md)
- [Knowledgeモデル](docs/knowledge-model.md)
- [自動capture](docs/automatic-capture.md)
- [Sandboxと読み取り専用構成](docs/sandbox.md)
- [プライバシーと公開前の検査](docs/privacy.md)
- [スキーマ](schemas/README.md)
- [完全に架空のデモLibrary](examples/demo-project/README.md)

不具合やドキュメントへの質問は[Issues](https://github.com/nennchakki/portable-agent-brain/issues)へ送れます。実際の会話履歴や知識、secretは投稿せず、架空のデータで再現手順を示してください。

## 用語

- **Library**：利用者が管理する、知識メモの保存ディレクトリ。
- **context**：今回のタスクでAgentへ渡すために選んだ知識。
- **candidate**：まだ人間が承認していない知識候補。
- **capture**：作業で得た知識を、検査して候補として残すこと。
- **履歴採掘**：過去の会話履歴から知識を探して抽出すること。v0.1.0では未実装。

## ライセンス

Portable Agent Brainは[MIT License](LICENSE)で公開しています。依存パッケージには、それぞれのライセンスが適用されます。
