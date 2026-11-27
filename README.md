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
|.github/workflows/deploy.yml|mainへのpushでテストし、Azure設定済みならデプロイ|

## Azure App Service への公開手順

現時点で Azure 実環境は未構築。厳密に0円で運用する場合は、利用可能な学校提供リソース・無料枠・支出上限を確認する。Storage の容量・操作・転送には料金が発生し得る。

1. Azure Portal で対象サブスクリプションを確認し、リソースグループを作成または選択。
2. Linux App Service プラン作成画面でリージョンと F1（無料）を選ぶ。F1 を選択できない場合は対象リージョンの無料 SKU の提供状況、サブスクリプションのクォータ、学校のポリシーを確認する。別の許可リージョンか既存の無料プランを選ぶ。
3. 同プランにコード方式の Web App（Python 3.12）を作成し、HTTPS Only とシステム割り当てマネージド ID を有効化。
4. 課金条件の承認後に汎用 v2 の Standard LRS Storage Account を作成するか、学校指定の既存アカウントを使う。テーブル posts と非公開の Blob コンテナー images を作成する。
5. Web App の ID に posts で Storage Table Data Contributor、images で Storage Blob Data Contributor を割り当てる。
6. Web App の環境変数に STORAGE_MODE=azure、AZURE_STORAGE_ACCOUNT（アカウント名）、SECRET_KEY（各環境で生成した長いランダム値）、SCM_DO_BUILD_DURING_DEPLOYMENT=true を登録。テーブル名・コンテナー名を変更した場合は .env.example の変数を設定。接続文字列を使う場合は App Service の秘密設定だけに登録する。
7. スタートアップコマンドを `gunicorn --bind 0.0.0.0:8000 app:app` に設定し保存。
8. デプロイ用の Entra アプリまたはユーザー割り当て ID に Web App スコープの Website Contributor を付与。フェデレーション資格情報の発行者を https://token.actions.githubusercontent.com 、対象者を api://AzureADTokenExchange 、対象を GitHub リポジトリの main ブランチに設定する。
9. GitHub の Settings → Secrets and variables → Actions → Variables に AZURE_WEBAPP_NAME、AZURE_CLIENT_ID、AZURE_TENANT_ID、AZURE_SUBSCRIPTION_ID を登録。main への push または Actions の手動実行でテスト後に ZIP をデプロイする。
10. Portal 表示の既定ドメインで /static/index.html と / を開く。画像付き投稿と回答を作成し、Table と Blob の両方を確認する。再起動後の表示を確認し、要件定義のサイトURLを更新する。503 の場合は環境変数、データ権限、ネットワーク許可を確認する。

[App ServiceのPython公開手順](https://learn.microsoft.com/ja-jp/azure/app-service/quickstart-python) · [GitHub ActionsとOIDC](https://learn.microsoft.com/ja-jp/azure/app-service/deploy-github-actions) · [Azure Tables](https://learn.microsoft.com/ja-jp/azure/storage/tables/) · [Azure Blob](https://learn.microsoft.com/ja-jp/azure/storage/blobs/)

## 動作確認

`python -m unittest discover -s tests -v`。SQLite で投稿・再読込、画像、回答、絞り込み、権限、解決済み、CSRF、連続送信、入力エラーを検証する。開発時に Azurite で Table の追加・照会と Blob のアップロード・取得も確認した。Azure 実環境の認証・権限・デプロイは未検証。
