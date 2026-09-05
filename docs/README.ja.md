# 説明書一覧

[English](README.md) | 日本語 | [プロジェクトのREADME](../README.ja.md)

目的に合う項目を選んでください。ここに載せた説明は、すべて英語版と日本語版があります。初めて設定する方は、詳しい使い方を読むか、セットアップ用プロンプトをAIへ渡せば始められます。迷ったら、入門ガイドからどうぞ。

## 最初に読む

| 内容 | 日本語 | English |
|---|---|---|
| 初期設定、普段の使い方、困ったときの確認 | [初めての設定と使い方](guide.ja.md) | [English](guide.md) |
| AIに設定と最初のメモ作りを任せる | [セットアップ用プロンプト](../prompts/setup-and-import.ja.md) | [English](../prompts/setup-and-import.md) |
| コマンドを使った導入と設定項目 | [コマンド中心の導入手順](getting-started.ja.md) | [English](getting-started.md) |

## 使い方を調べる

| 内容 | 日本語 | English |
|---|---|---|
| 全機能とコマンド、Hermes-Agentとの違い | [機能・コマンドの解説](features.ja.md) | [English](features.md) |
| 既存の設定を残してAIを接続・解除する | [AIごとの接続方法](agent-integration.ja.md) | [English](agent-integration.md) |
| AIに正式な接続方法を調べてもらう | [接続用プロンプト](../prompts/connect-agent.ja.md) | [English](../prompts/connect-agent.md) |
| 自分のprivate GitHubへ接続し、確認して送る | [private GitHubへの保存](github-sync.ja.md) | [English](github-sync.md) |
| 作業後に役立つことをメモへ残す | [作業後のメモの保存](automatic-capture.ja.md) | [English](automatic-capture.md) |
| メモの種類、リンク、検索時の優先順 | [メモの書式](knowledge-model.ja.md) | [English](knowledge-model.md) |
| コンテナやアクセス制限のある環境から使う | [隔離された実行環境](sandbox.ja.md) | [English](sandbox.md) |
| 非公開データの扱いと公開前の検査 | [プライバシー](privacy.ja.md) | [English](privacy.md) |

## 書式と見本

| 内容 | 日本語 | English |
|---|---|---|
| 接続したAIが読む共通の指示 | [AI指示書の参照訳](../adapters/external-brain.ja.md) | [English](../adapters/external-brain.md) |
| ツールが受け付けるデータ形式 | [データの書式定義](../schemas/README.ja.md) | [English](../schemas/README.md) |
| 自分のメモ保存先に置くもの | [保存先の書式見本](../templates/library/README.ja.md) | [English](../templates/library/README.md) |
| 架空のメモを使ってコマンドを試す | [デモ用の保存先](../examples/demo-project/README.ja.md) | [English](../examples/demo-project/README.md) |

コマンド名、JSON・YAMLの項目名、実際にコピーして使う `TEMPLATE.md`、デモのグラフ用メモは、日英で共通です。これらを別々に複製すると、IDが重複したり書式がずれたりするため、説明するREADMEだけを翻訳しています。

日本語のAI指示書は、人が内容を確認するための参照訳です。どの言語の説明を使う場合も、実際のAI接続先は共通の英語版 `adapters/external-brain.md` です。
