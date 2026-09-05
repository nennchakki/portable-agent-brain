# private GitHubへの保存

[English](github-sync.md) | 日本語 | [説明書一覧](README.ja.md)

自分のGitHubアカウントで、好きな名前の既存privateリポジトリへ接続できます。
公開ソフト本体と、自分のメモは別フォルダ・別Gitリポジトリに置きます。
検索やメモ保存には、GitHub・GitHub CLI・ネットワークは不要です。

## コマンド一覧

| コマンド | 操作 | メモ本文の送信 |
|---|---|---|
| `brain github connect --repo OWNER/REPO` | privateへのアクセスを検証し、接続先を登録する | なし |
| `brain github status` | 公開範囲・ID・書き込み権限を再確認する | なし |
| `brain github push` | 送信するコミットと差分を表示する | なし |
| `brain github push --approve DIGEST` | プレビューで確認した内容を再検証して送る | 送信するコミットがある場合に実行 |

`--library /absolute/path/to/notes` でメモのフォルダを明示できます。
どのコマンドも `--remote NAME` と `--json` に対応します。
`DIGEST` はプレビューに表示されたapproval値に置き換えます。
表示された送信用コマンドをそのまま使えば、同じエンジンと保存先を指定できます。

ソースを取得したフォルダから直接使う場合は `./brain`、別フォルダへ移動した後はその `brain` の絶対パスを使います。
単に `brain` と呼ぶ場合は、この版が実行されることを確認してください。[導入手順](getting-started.ja.md)も参照できます。

## 接続する

Gitと[GitHub CLI](https://cli.github.com/)を用意し、
`gh auth login --hostname github.com` でログインしてください。
認証情報はGitHub CLIが管理します。Brainはメモにトークンを保存したり、認証の出力を表示したりしません。
GitHubで先にprivateリポジトリを作るか、自分が書き込める既存のprivateリポジトリを選びます。
Brain自体はGitHubのリポジトリを作りません。初めてのバックアップには、空の接続先が扱いやすいです。

以下の `example-owner/my-notes` は架空の例です。自分の接続先に置き換えてください。

```sh
brain github connect --library "$HOME/agent-library" --repo example-owner/my-notes
brain github status --library "$HOME/agent-library"
```

メモのフォルダは先に作っておきます。新規なら `brain init` が使えます。
接続時、必要ならローカルGitを `main` ブランチで初期化します。
`origin` がなければ追加し、確認済みリポジトリIDをローカルGit設定の
`remote.origin.brainRepositoryId` へ記録します。既存のコミットを残し、別の接続先やIDへの置き換えは拒否します。
別のremote名には `--remote backup` を使います。接続だけではメモ本文を送りません。
`status` はオンラインでprivateとアクセス権を再確認します。

`setup --git-mode remote --remote-url https://github.com/example-owner/my-notes.git`
も同じprivate検証を通ります。URLの登録だけをしていた初期0.1.0からの仕様変更です。
以前に登録した接続先も、管理されたpushを使う前に `github connect` で検証・登録してください。
`none`・`local`・`existing` は従来どおりローカル設定を扱い、管理されたpushの接続承認にはなりません。

初期版は `github.com` のHTTPS接続に対応します。
public・internal・アーカイブ済み・無効・書き込み権限のない接続先は拒否します。
認証失敗、ネットワーク障害、API応答の不備で確認できない場合も停止します。
接続確認に失敗しても、ローカルでのメモ保存は使えます。

## 内容を確認して送る

送信前にファイルを確認し、送りたい変更をローカルでコミットします。
この機能はstage・commit・pull・merge・force pushを行いません。
未追跡のメモを含め、未コミットの変更がある場合はプレビューを止めます。
保存できたと誤解したまま、新しいメモが送信対象から漏れるのを防ぐためです。

```sh
cd "$HOME/agent-library"
git status --short
git diff
# 意図したファイルだけをstageし、git diff --cachedで確認してからcommitする。
brain github push --library "$HOME/agent-library"
```

最後のコマンドは**プレビューだけで、まだ送信しません**。
接続先のブランチIDを読み、これから送る各コミットとファイルの履歴を点検します。
コミットID、点検対象のファイル一覧、差分全文、`--approve` を含む送信用コマンドを表示します。
一覧には各時点で点検した未変更ファイルも含まれます。変更内容は差分で確認してください。
コミットの作成者情報や本文も含めて確認し、表示されたコマンドを実行すると、その内容を送ります。
`--json` では同じ情報を構造化した形式で取得できます。

approval値は、保存先・remote・リポジトリID・ブランチ・ローカルと接続先のコミットID・点検した内容を結びつけます。
変更を検出する値であり、認証用の秘密情報でも、人が内容を読んだ証明でもありません。
AIから送信する場合も、確認した内容の送信について利用者の承認を得てください。

送信操作でもprivate・アクセス権・ID・送信内容を再検証します。
変化があれば、新しいプレビューの確認が必要です。
現在のローカルブランチの確定したコミットだけを、GitHub上の同名ブランチへ送ります。
ほかのブランチやタグは送りません。すでに一致していれば送信しません。
ブランチのupstreamは設定しません。

## 止まったとき

| 状態 | 対処 |
|---|---|
| privateへのアクセスを確認できない | `gh` のログイン、公開範囲、権限、ネットワークを確認。ローカルのメモは使えます。 |
| 検証済みの接続がない | `github connect` で既存の接続先を検証・登録します。 |
| 未コミットの変更がある | 意図したファイルを確認してコミットし、再度プレビューします。 |
| 接続先の履歴が手元にない・分岐している | 選んだremoteをfetchし、履歴を確認して整合させます。自動で競合解決や上書きはしません。 |
| 確認後に内容が変わった | 新しいプレビューを読み、新しいapproval値を使います。 |
| URLやリポジトリIDが変わった | Git設定とGitHub側の現在の接続先を調べてから再接続します。 |
| 未対応のGit設定がある | ローカルのURL書き換え・HTTP・認証設定の目的を確認してください。設定をむやみに削除しないでください。 |
| 送信失敗・タイムアウト | 接続先のブランチを確認して、再度プレビューします。応答を失う前に送信が受理されている場合があります。 |

## 対応範囲

- 通常の完全なGitリポジトリを使います。shallow clone、linked worktree、旧式のgrafts、シンボリックリンク、submoduleは未対応です。
- UTF-8テキストが対象です。1ファイルと表示する差分は各1,000,000バイトまで、送信コミットは200件、異なるblobは2,000件、本文走査の合計は20,000,000バイトまでです。
  上限を超えた内容を黙って飛ばしません。小さく確認できる範囲に整理してください。
- 最終版で削除された途中の内容、コミット情報、代表的な認証情報のパターンや秘密・実行時ファイル名も点検します。
  すべての個人情報を検出する仕組みではないので、privateへの送信でも内容確認は必要です。
- 通信は確定したHTTPSの接続先とGitHub CLIの認証を使い、TLSを検証し、HTTPリダイレクトを禁止します。
  管理された操作ではsystem/global Git設定と継承した `GIT_*` の上書きを除外します。
  ローカルのURL書き換え・HTTP・認証の上書きがある場合は拒否します。グローバル設定自体は変更しません。
- private確認とpushは別の通信です。その間の公開範囲変更や、所有者が将来publicへ変えることまで防げません。
  直接のGit操作やほかのアプリも制御しません。pre-push hookや常時監視は設置しません。

publicの接続先を勝手にprivateへ変更することはありません。
公開後にprivateへ変更しても、過去の公開を取り消せません。[プライバシー](privacy.ja.md)も参照してください。

仕様の根拠：[GitHubのリポジトリ情報](https://docs.github.com/en/rest/repos/repos#get-a-repository)、
[GitHub CLIの認証](https://cli.github.com/manual/gh_auth_login)、[Git push](https://git-scm.com/docs/git-push)。
