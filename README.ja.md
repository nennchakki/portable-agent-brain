# Portable Agent Brain

[English](README.md) | 日本語

私はHermes-agentを使っていても、結局いろんなAIをぐるぐる試してしまいます。そのたびに、それまで蓄積した知識がリセットされるのがつらくて、これを作りました。

使うAIを替えても、知識はそのまま持っていきたい。なので、知識をAIの外にMarkdownで保存して、次のAIにも読んでもらうようにしています。

## とりあえず使う

どうせ長い説明は読まないと思うので、ひとまずこれを打ってください。
macOSかLinuxと、Python 3.11以上が必要です。

```sh
git clone https://github.com/nennchakki/portable-agent-brain.git
cd portable-agent-brain
./brain setup
```

あとは保存先や使うAIを選んでください。Claude CodeとCodexはここで接続できます。ほかのAIを使う場合は[接続手順](docs/agent-integration.md)をどうぞ。

最初は空の状態です。作業後の短い要約から知識候補を残し、次のタスクでは関係するメモだけをAIに読んでもらいます。

## 少しだけ補足

- 知識は手元の別フォルダに保存します。この公開リポジトリには、私の知識や会話履歴は入っていません。
- Git remoteは任意です。バックアップするならprivateリポジトリを使ってください。
- 新しい知識は確認待ちの候補として保存します。勝手に恒久ルールへ昇格させません。
- **過去の会話履歴を自動で取り込む機能はまだありません。** `--history-source`も手順を表示するだけで、履歴の中身は読みません。

詳しく知りたくなったら、[導入手順](docs/getting-started.md)・[知識の保存](docs/automatic-capture.md)・[プライバシー](docs/privacy.md)をどうぞ。詳細ドキュメントは英語です。

不具合や質問は[Issues](https://github.com/nennchakki/portable-agent-brain/issues)へ。秘密情報や実際の会話ログは貼らないでください。

[MIT License](LICENSE)
