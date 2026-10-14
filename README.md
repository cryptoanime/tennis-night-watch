無料クラウド版（PCを閉じても動く）

GitHubの公開リポジトリと標準GitHub Actionsランナーを使います。
非公開リポジトリでは無料実行時間の上限があるため、この構成の無料運用対象外です。
支払い方法の登録や有料ランナーは不要です。
コードは公開されます。メールアドレスとアプリパスワードはSecretsに保存します。

1. GitHubで公開リポジトリ「tennis-night-watch」を作成。
2. このフォルダの内容をリポジトリの直下に置きます。
   watch.py、config.json、requirements.txtと.github/workflows/watch.ymlが必要です。
   .githubフォルダは隠しフォルダなのでアップロード漏れに注意してください。
   config.jsonにはメールアドレス・パスワードを入力しないでください。
3. Settings → Secrets and variables → Actions → New repository secretで設定。
   TENNISU：送信元Gmail
   TENISU3：そのGmailで発行したアプリパスワード（通常のパスワードではありません）
   TENISU2：通知先Gmail
   アプリパスワードにはGoogleの2段階認証が必要です。一部アカウントでは利用不可です。
   パスワードはチャット・公開ファイル・コメントに書かないでください。
4. Actions → Tennis night availability → Run workflowで動作確認。
   初回時点で空きがあればメールが届きます。全コート×なら空きメールは届きません。
   ログの当日日付・12コートの結果と成功を確認してから監視開始と判断してください。
   SMTP設定のテストはPCでpython watch.py --test-emailでも可能です。

自動実行：毎日、日本時間9:02〜20:57、5分間隔を指定。
無料環境では実行が遅れたり、混雑時にスキップされる場合があります。
5分以内の通知は保証しません。即時検知サービスではありません。
公開リポジトリで60日間操作・変更がないと定期実行が無効になる場合があります。
Actions画面の状態を定期的に確認してください。止まった場合は再有効化が必要です。
前回結果はActionsキャッシュに保存。キャッシュが削除されると空きを再通知し得ます。
クラウド版は失敗をActionsの失敗として表示します。連続失敗メールはPC常駐版のみです。
停止：Actionsの対象ワークフローでDisable workflow。
Secretsとメール設定が未入力のままでは監視・通知は開始できません。

公式資料：
https://docs.github.com/en/actions/concepts/billing-and-usage
https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows
https://support.google.com/accounts/answer/185833?hl=ja

現在の検証：サイト12面の手動確認、構文、通知判定は確認済み。
2026年10月14日、クラウドから12面取得とGmailテストメール送信の成功を確認済み。

開始手順追加：Actionsでmode=checkを実行して12面取得を確認。Secrets登録後mode=test-emailで送信テスト。最後にSettings → Secrets and variables → Actions → VariablesへMONITOR_ENABLED=trueを登録すると定期監視が有効になります。
