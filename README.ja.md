# Portable Agent Brain

[English](README.md) | 日本語

私はHermes-agentを使っていても、結局いろんなAIをぐるぐる試してしまいます。そのたびに、それまで蓄積した知識がリセットされるのがつらくて、これを作りました。

使うAIを替えても、知識はそのまま持っていきたい。なので、知識をAIの外にMarkdownで保存して、次のAIにも読んでもらうようにしています。

## とりあえず使う

どうせ長い説明は読まないと思うので、ひとまずこれを打ってください。
macOSかLinuxと、Python 3.11以上が必要です。

```sh
git clone --branch feat/initial-public-release https://github.com/nennchakki/portable-agent-brain.git
cd portable-agent-brain
./brain setup
```

あとは保存先や使うAIを選んでください。Claude CodeとCodexはここで接続できます。ほかのAIを使う場合は[接続手順](docs/agent-integration.md)をどうぞ。

AIに設定と過去の履歴からのメモ作りまで任せるなら、[このプロンプト](prompts/setup-and-import.ja.md)を渡してください。Obsidianでメモ同士の関連をたどるところまで頼めます。

最初は空の状態です。作業でわかったことを短いメモとして残し、次の作業では関係するメモだけをAIに読んでもらいます。

![Obsidianのグラフ表示でつながるメモ](docs/images/obsidian-graph.png)

Obsidianで既存のメモを表示した例です。導入直後は空の状態から始まります。

## 少しだけ補足

- 知識は手元の別フォルダに保存します。この公開リポジトリには、私の知識や会話履歴は入っていません。
- Gitでの同期は必須ではありません。バックアップ先を作るなら、非公開のリポジトリにしてください。
- 保存したメモは、人が確認するまで参考情報として扱います。AIが勝手に作業の決まりにすることはありません。
- CLIに履歴の自動取り込み機能はありません。`--history-source`は手順の表示だけです。上のプロンプトでは、許可した履歴をAIが読んで要約します。

操作を一つずつ確認したい方は、[初心者向けの詳しい使い方](docs/guide.ja.md)へ。[英語版](docs/guide.md)もあります。技術的な説明は[導入手順](docs/getting-started.md)・[知識の保存](docs/automatic-capture.md)・[プライバシー](docs/privacy.md)をどうぞ。

不具合や質問は[Issues](https://github.com/nennchakki/portable-agent-brain/issues)へ。秘密情報や実際の会話ログは貼らないでください。

[MIT License](LICENSE)
