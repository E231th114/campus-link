# Campus Link

高校生の質問・回答掲示板。6カテゴリ、ニックネーム投稿、検索、新着順・人気順、未回答フィルタ、リアクション、通報、解決済み、画像添付に対応。

## 0円で試す

Python 3.10〜3.12 の環境で以下を実行する。

```sh
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m flask --app app run --port 5187
```

[ローカル掲示板](http://127.0.0.1:5187/) を開く。SQLite、画像、署名鍵は instance/ に保存する。初回の一覧は空。投稿者の操作権限はブラウザの署名付き Cookie で識別する。Cookie を削除すると解決済みに変更する権限を失う。通報は保存先の report パーティションで運営者が確認する。投稿者は確認操作を経て論理削除できる。削除後は本文・画像・回答を公開しない。運営者向け管理画面は未実装。

静的見本は static/index.html を直接開くか、起動中の /static/index.html を開く。サンプルは実投稿と独立している。

## ファイル構成

|パス|役割|
|---|---|
|requirements.md|学校指定形式の要件定義|
|app.py / templates/|Flaskのルート、入力検証、一覧・詳細・投稿・エラー画面|
|services/store.py|SQLite／Azure Table とローカル画像／Azure Blob の読み書き|
|static/|静的見本、共通CSS、送信時の表示|
|tests/|投稿から解決までの機能・権限テスト|
|.github/workflows/deploy.yml|mainへのpushでテストし、Azureの認証設定と有効化後にデプロイ|

## Azure App Service への公開手順

指定された公開URLは確認済みですが、現在はApp Serviceの初期Welcomeページを返しており、Campus Linkのデプロイ完了は未確認です。Azure CLIはこのPCにありません。厳密に0円で運用する場合は、利用可能な学校提供リソース・無料枠・支出上限を確認する。Storage の容量・操作・転送には料金が発生し得る。

1. Azure Portal で対象サブスクリプションを確認し、リソースグループを作成または選択。
2. Linux App Service プラン作成画面でリージョンと F1（無料）を選ぶ。F1 を選択できない場合は対象リージョンの無料 SKU の提供状況、サブスクリプションのクォータ、学校のポリシーを確認する。別の許可リージョンか既存の無料プランを選ぶ。
3. 同プランにコード方式の Web App（Python 3.12）を作成し、HTTPS Only とシステム割り当てマネージド ID を有効化。
4. 課金条件の承認後に汎用 v2 の Standard LRS Storage Account を作成するか、学校指定の既存アカウントを使う。テーブル posts と非公開の Blob コンテナー images を作成する。
5. Web App の ID に posts で Storage Table Data Contributor、images で Storage Blob Data Contributor を割り当てる。
6. Web App の環境変数に STORAGE_MODE=azure、AZURE_STORAGE_ACCOUNT（アカウント名）、SECRET_KEY（各環境で生成した長いランダム値）、SCM_DO_BUILD_DURING_DEPLOYMENT=true を登録。テーブル名・コンテナー名を変更した場合は .env.example の変数を設定。接続文字列を使う場合は App Service の秘密設定だけに登録する。
7. スタートアップコマンドを `gunicorn --bind 0.0.0.0:8000 app:app` に設定し保存。
8. デプロイ用の Entra アプリまたはユーザー割り当て ID に Web App スコープの Website Contributor を付与。フェデレーション資格情報の発行者を https://token.actions.githubusercontent.com 、対象者を api://AzureADTokenExchange 、対象を GitHub リポジトリの main ブランチに設定する。
9. GitHub の Settings → Secrets and variables → Actions → Variables に AZURE_DEPLOY_ENABLED=true、AZURE_WEBAPP_NAME、CAMPUS_LINK_URL、OIDCを使う場合は AZURE_CLIENT_ID、AZURE_TENANT_ID、AZURE_SUBSCRIPTION_ID を登録する。OIDCを使わない場合は AZURE_PUBLISH_PROFILE をSecretに登録する。発行プロファイルはAzure PortalのDeployment Centerから取得し、ファイル内容をログやリポジトリに保存しない。
10. mainへのpushまたはActionsの手動実行でテスト後にデプロイする。テスト失敗時はデプロイジョブが起動しない。OIDC変数が揃っている場合はOIDCを優先し、揃っていない場合だけ発行プロファイル方式を使う。
11. `CAMPUS_LINK_URL` の `/`、`/static/index.html`、`/guide` を開き、GitHub Actionsのsmoke-testがCampus Linkのタイトル、CSS、ガイドを確認する。画像付き投稿と回答を作成し、TableとBlobの両方を確認する。再起動後の表示を確認する。503の場合は環境変数、データ権限、ネットワーク許可を確認する。

[App ServiceのPython公開手順](https://learn.microsoft.com/ja-jp/azure/app-service/quickstart-python) · [GitHub ActionsとOIDC](https://learn.microsoft.com/ja-jp/azure/app-service/deploy-github-actions) · [Azure Tables](https://learn.microsoft.com/ja-jp/azure/storage/tables/) · [Azure Blob](https://learn.microsoft.com/ja-jp/azure/storage/blobs/)

## 動作確認

`python -m unittest discover -s tests -v`。SQLite で投稿・再読込、画像、回答、絞り込み、権限、解決済み、CSRF、連続送信、入力エラーを検証する。開発時にAzuriteでTableの追加・照会とBlobのアップロード・取得も確認した。Azure実環境の認証・権限・デプロイは未検証。ワークフローのsmoke-testはデプロイ成功時だけ実行する。

### GitHubからAzureへ自動公開

mainへのpushで `test` が実行され、成功した場合だけデプロイ候補が起動します。`concurrency` により本番デプロイは同時に1つだけ進みます。OIDCジョブには `id-token: write` だけを付与し、発行プロファイル方式ではAzureのSecretをGitHub Actions内でのみ利用します。現在は `AZURE_DEPLOY_ENABLED` を未設定のため自動デプロイを停止しています。指定URLは初期Welcomeページを返しており、Azure認証情報とApp Service設定が必要です。

App Serviceには次を設定します。

```text
Startup Command: gunicorn --bind=0.0.0.0:8000 app:app
SCM_DO_BUILD_DURING_DEPLOYMENT: 1
STORAGE_MODE: azure
AZURE_STORAGE_ACCOUNT: <Storage Account名>
AZURE_TABLE_NAME: posts
AZURE_CONTAINER: images
SECRET_KEY: <App ServiceのSecret設定に保存したランダム値>
```

Table Storage Data ContributorとBlob Storage Data ContributorはApp ServiceのManaged Identityにだけ付与します。Azure Storageの接続文字列を使う場合も、App Serviceのアプリケーション設定に保存し、GitHubやコードには置きません。デモデータはデプロイ時に投入されません。必要なときだけ `python scripts/seed_demo.py --azure` を認証済みの管理端末から実行します。

## 使い方ガイド

ヘッダーの「？」またはPCの「使い方ガイド」から `/guide` を開けます。端末別の手順、架空のデータで撮影した画面例、FAQを収録しています。練習の進行位置は同じタブに保存され、掲示板への書き込みは発生しません。

UI変更時には templates/guide.html のボタン名と手順、static/guide/ の画像と番号、static/guide.js の練習内容を合わせて更新してください。

## デモデータ

デモデータは自動投入されません。ローカルで `python scripts/seed_demo.py` を明示的に実行すると、6カテゴリ各5件、回答、参考になった、絵文字、期限、画像のサンプルをSQLiteに追加します。再実行しても同じ行を更新するため重複しません。件数を6〜8件にする場合は `--count 8` を指定します。

削除は `python scripts/clear_demo.py --yes` です。`--yes` がない削除は拒否し、`demo` 識別子の付いた行と画像だけを対象にします。Azureへ投入するときだけ `--azure` を付け、App Service上では実行しないでください。Storageの接続情報は環境変数から読み、リポジトリには保存しません。実利用者の投稿は削除しません。

## 回答期限と絵文字

期限はサーバーがUTCのUnix秒で計算し、日本時間で表示する。回答時に削除・解決・受付停止・期限を判定する。残り1時間以内は「期限間近」。新しい投稿の board 行に deadline を保存し、旧投稿に属性がない場合は期限なし。投稿者による更新は deadlines パーティションの投稿ID行に保存する。

各投稿の emoji-投稿ID パーティションでは、利用者・絵文字・版番号の組で一意の行を追加する。追加と取り消しの履歴から利用者ごとの最新状態を集計する。端末は希望状態と表示時の版番号を送り、再送や遅れて到着した旧版の操作で最新状態が覆らないようにする。大量操作は送信元ごとに10秒間16変更まで。人気順は従来の like パーティションだけで計算する。

SQLiteの既存テーブルとAzure Table Storageの既存テーブルを利用し、移行コマンドは不要。期限・絵文字の仕様は services/discussion.py、フロントの操作は static/discussion.js を参照。リアクションは操作時と詳細表示時に集計するため、他の閲覧者の操作を常時プッシュする機能はない。履歴が大きくなった場合は集計コストの再評価が必要。

## 絵文字の利用制限と通報

Unicode Emoji 18.0 の [emoji-test.txt](https://unicode.org/Public/emoji/latest/emoji-test.txt) を data/unicode/ に同梱。fully-qualified の単一絵文字列に照合し、異体字セレクタを正規化する。独立した肌色部品、未定義の結合、自由文は登録できない。標準の肌色・性別・国旗・家族などは選択できる。おすすめ8種の保存キーは従来と同じ。

管理者は config/emoji_moderation.json の rules で識別子、コードポイント列、理由、enabled、更新日を管理する。初期制限は U+1F595（中指を立てるジェスチャー）。明示的な侮辱を理由に、肌色・表示形式を問わず制限する。食べ物・身体・医療用品などを俗語的な解釈だけで全面禁止しない。

文脈上の嫌がらせはピッカー内の「リアクションを通報」で記録する。report 行の post と emoji を確認し、特定投稿だけ非表示にする場合は hidden_by_post の投稿UUIDに絵文字IDの配列を設定する（例：{"投稿UUID":["heart","u-1f98b"]}）。設定変更はデプロイ管理権限を持つ管理者がレビューして再デプロイする。設定編集用の公開APIはない。履歴は消去せず、非表示を解除すると元の状態が再び集計される。

カテゴリ・検索・最近使用・投稿別集計はサーバーが許可した候補だけを使用する。最近使用は端末内に最大24件。変更操作への10秒16回の制限は追加・取り消しで共通。
