# AIごとの接続方法

[English](agent-integration.md) | 日本語 | [説明書一覧](README.ja.md)

## 共通の指示書

どのAIにも、同じ短い指示書を使います。

```text
portable-agent-brain/adapters/external-brain.md
```

実際の接続に使うファイルは、すべてのAIでこの英語版です。[日本語の参照訳](../adapters/external-brain.ja.md)もありますが、別の接続先ではありません。

指示書には自分のメモを入れません。AIの共通設定には、このファイルへの参照だけを追加してください。保存先全体を読み込ませたり、各AIの設定へ指示書の本文を何度もコピーしたりしないでください。

## setupで接続する

```sh
./brain setup
```

通常は対話形式で接続するAIを選べます。接続先を明示する例は次のとおりです。

```sh
./brain setup --agent claude --claude-file /absolute/path/to/CLAUDE.md
./brain setup --agent codex --codex-file /absolute/path/to/AGENTS.md
./brain setup --agent generic \
  --generic-agents-file /absolute/path/to/AGENTS.md
```

setupは次の範囲だけを変更します。

- 変更前のファイルをバックアップする。
- 既存の文章、hooks、権限、モデル設定を残す。
- 管理対象であることがわかる目印付きの参照を1つだけ追加する。
- 同じ設定を再実行しても重複を作らない。
- 指示書の場所と `brain` コマンドが使えるかを確認する。
- 途中で失敗した場合は、自身が行った変更だけを戻す。

同じAIが複数の親フォルダにある設定を読む場合、同じ共通設定をそれぞれへ追加しないでください。実際に使われる設定ファイルを1つ選びます。

## Claude Code

使っている版が外部のMarkdownを読み込む仕組みに対応していることを確認できた場合、次のような絶対パスの参照を使います。

```text
@/absolute/path/to/portable-agent-brain/adapters/external-brain.md
```

setupは実際の場所を確認して絶対パスにします。指示書の本文を `CLAUDE.md` へコピーしません。

通常の接続先は `~/.claude/CLAUDE.md` です。別のファイルを使う場合は、Claude Codeがそのファイルを読むことを先に確認し、`--claude-file` で指定します。現在の読み込み方法は[Claude Codeの公式説明](https://code.claude.com/docs/en/memory)でも確認してください。

設定後は新しいセッションを始め、次の2点を試します。

1. 過去のメモが役立つ作業で、必要な範囲の `brain context` を使える。
2. 明らかな誤字修正では、メモの検索を省く。

最初から保存先全体を読み込んではいけません。

## Codex

Codexには、`AGENTS.md` へ次のような短い参照を追加します。

```text
<!-- portable-agent-brain:start -->
## External Brain

For non-trivial work where prior project knowledge could change the result,
read `<ADAPTER_PATH>` and follow it. Do not preload the knowledge library.
<!-- portable-agent-brain:end -->
```

`<ADAPTER_PATH>` は実際の共通指示書の絶対パスに置き換えます。この目印の外側にある文章は変更しません。

同じ範囲に内容のある `AGENTS.override.md` があると、通常の `AGENTS.md` より優先される場合があります。この場合、setupは勝手に接続先を決めず、明示的な指定を求めます。別の確認済みファイルを使うときは `--codex-file` で指定します。標準ではプロジェクト内の `AGENTS.md` を変更しません。

現在の読み込み順は[Codexの公式説明](https://learn.chatgpt.com/docs/agent-configuration/agents-md)で確認してください。設定後は新しいタスクを始め、過去の判断が必要な依頼ではメモを探し、明らかな誤字修正では省くことを確認します。

## `AGENTS.md` を読むほかのAI

Kimiなど、ほかのAIがユーザー共通の `AGENTS.md` を読む場合があります。製品の公式説明で、次の点を先に確認してください。

- ユーザー共通の設定ファイルがあるか。
- どのパスを読むか。
- プロジェクト内の設定や別のファイルとの優先順位。

確認できたファイルは、次のように明示して接続できます。

```sh
./brain setup --agent generic \
  --generic-agents-file /absolute/path/to/AGENTS.md
```

ファイル名だけを見て接続先を推測しないでください。対応する読み込み方法がない場合は、そのAIが正式に提供する設定方法か、次の接続用プロンプトを使います。

## 専用手順がないAI

[接続用プロンプト](../prompts/connect-agent.ja.md)を、そのAIへ一度だけ渡してください。プロンプトでは次の作業を依頼します。

- そのAIの現在の共通設定の仕組みを確認する。
- 既存設定を残してバックアップする。
- 共通の指示書への短い参照だけを追加する。
- 保存先がAIの実行環境から見えることを確認する。
- 再実行しても設定が重複しないようにする。
- 新しいセッションで動作を確認し、戻し方を報告する。

接続だけでなく、初期設定と許可した履歴からのメモ作りまで任せる場合は、[セットアップ用プロンプト](../prompts/setup-and-import.ja.md)を使ってください。

## 作業が終わったときにメモを保存する

接続したAIは、意味のある作業を終えたときだけ、次にも役立つことがあるか判断します。あれば、会話の原文ではなく短いJSON要約を `brain learn-extract` へ渡します。

保存忘れを通知する任意のstop hookもあります。ただし、安全なhookが行うのは、結果マーカーがあるかを一度確認して、なければ同じAIへ判断を促すことだけです。

hookは次のことをしてはいけません。

- 会話やツールの出力を読み取って保存する。
- 別のAIや外部サービスを呼ぶ。
- メモを直接作る。
- AIがまだ作業中なのに繰り返し通知する。
- 確認待ちのメモを自動で承認、統合、置き換え、commitする。

AIは最後に、次のいずれかを示すマーカーを1つだけ返します。

```text
<!-- brain-capture:v1 saved|duplicate|reinforced|none|error -->
```

意味は、`saved` が新規保存、`duplicate` が既存内容との重複、`reinforced` が別の作業による根拠の追加、`none` が保存不要、`error` が失敗です。hookの導入は任意です。

## メモの保存先を決める順序

`brain` は次の順で保存先を決めます。

1. コマンドの `--library`。
2. 環境変数 `BRAIN_LIBRARY`。
3. setupで保存した場所。
4. どれも指定されていない場合は `~/agent-library`。

コンテナやsandboxでは、ホスト側のパスではなく、その環境の中から見えるパスを使います。詳しくは[隔離された実行環境](sandbox.ja.md)を参照してください。

## 接続を外す

設定を戻すときは、次の順で、自分が追加したものだけを外します。

1. `portable-agent-brain:start` と `portable-agent-brain:end` で囲まれた部分を正確に削除する。
2. Claude Codeなどへ追加した共通指示書の読み込み行だけを削除する。
3. hookを追加した場合は、該当する項目だけを削除する。
4. `brain` コマンドへのリンクやラッパーを追加した場合は、対象を確認してからそれだけを削除する。
5. 個別に戻せない場合だけ、変更前のバックアップと現在の内容を比べて復元する。

設定ファイル全体やhooksファイル全体を、Portable Agent Brainを外すためだけに置き換えないでください。自分のメモは別のフォルダにあるため、接続を外しても削除する必要はありません。
