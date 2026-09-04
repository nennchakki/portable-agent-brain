# Portable Agent Brain

[English](README.md) | 日本語

私はHermes-agentを使っていても、結局いろんなAIをぐるぐる試してしまいます。そのたびに、それまで蓄積した知識がリセットされるのがつらくて、これを作りました。

使うAIを替えても、知識はそのまま持っていきたい。なので、知識をAIの外にMarkdownで保存して、次のAIにも読んでもらうようにしています。

## セットアップ：AIにこれを貼る

どうせ長い説明は読まないと思うので、使いたいAIにこれを貼ってください。ターミナルに打つコマンドではありません。

```text
Portable Agent Brainをセットアップして、今までのチャットや作業履歴から、
次のAIにも引き継げるメモを作ってください。

https://github.com/nennchakki/portable-agent-brain

リポジトリの prompts/setup-and-import.ja.md を読み、
「実行するAIへの指示」に従ってください。

あなたが普段読む設定ファイルに共通の指示書への参照を追加し、
利用してよい履歴を私に確認してから、最初のメモの保存まで進めてください。
メモはObsidianでも関連をたどれるようにしてください。
説明は短く、できたことと、私の操作が必要なところを最後に教えてください。
```

ファイルの読み書きとコマンド実行ができるAI向けです。できない操作は、あなたが行う手順を案内します。[英語のプロンプト](README.md#setup-paste-this-into-your-ai)・[実行するAI向けの詳しい指示](prompts/setup-and-import.ja.md)

### 自分で設定するなら

macOSかLinuxと、Python 3.11以上、Gitが必要です。

```sh
git clone https://github.com/nennchakki/portable-agent-brain.git
cd portable-agent-brain
./brain setup
```

あとは保存先や使うAIを選んでください。Claude CodeとCodexはここで接続できます。ほかのAIを使う場合は[接続手順](docs/agent-integration.md)をどうぞ。

最初は空の状態です。作業でわかったことを短いメモとして残し、次の作業では関係するメモだけをAIに読んでもらいます。

![Obsidianのグラフ表示でつながるメモ](docs/images/obsidian-graph.png)

Obsidianで既存のメモを表示した例です。導入直後は空の状態から始まります。

## 少しだけ補足

- 知識は手元の別フォルダに保存します。この公開リポジトリには、私の知識や会話履歴は入っていません。
- Gitでの同期は必須ではありません。バックアップ先を作るなら、非公開のリポジトリにしてください。
- 保存したメモは、人が確認するまで参考情報として扱います。AIが勝手に作業の決まりにすることはありません。
- CLIに履歴の自動取り込み機能はありません。`--history-source`は手順の表示だけです。上のプロンプトでは、許可した履歴をAIが読んで要約します。

詳しい説明は、[初めての設定と使い方](docs/guide.ja.md)と[機能・コマンドの解説](docs/features.ja.md)に分けています。[Hermes-Agentとの違い](docs/features.ja.md#hermes-agentとの違い)も後者にあります。どちらも英語版へのリンク付きです。

不具合や質問は[Issues](https://github.com/nennchakki/portable-agent-brain/issues)へ。秘密情報や実際の会話ログは貼らないでください。

[MIT License](LICENSE)
