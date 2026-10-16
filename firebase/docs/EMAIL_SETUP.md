# 讓 Firebase Functions 自動寄送簽署邀請 Email

系統會讀取 `firebase\functions\.env` 裡的 SMTP 設定。**沒有設定就不寄信**，管理台一樣會顯示每一方的簽署連結，讓你手動轉交。

## 方法 A：用 Gmail 寄（最簡單）

1. 你的 Google 帳號要先開啟「兩步驟驗證」：<https://myaccount.google.com/security>
2. 建立「應用程式密碼」：<https://myaccount.google.com/apppasswords>，名稱輸入 `MyContractApp`，會得到一組 **16 碼密碼**（只顯示一次）。
3. 用記事本打開 `firebase\functions\.env`，在最後加上以下 5 行（換成你的 Gmail 與 16 碼密碼，密碼不要有空格）：

```
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=你的帳號@gmail.com
SMTP_PASSWORD=abcdefghijklmnop
SMTP_FROM=全球化合約管理系統 <你的帳號@gmail.com>
```

4. 存檔後再雙擊一次 `deploy.cmd`。腳本會**保留**這些 SMTP 設定，只更新其他項目。

Gmail 個人帳號每天約可寄 500 封。

## 方法 B：用公司信箱或寄信服務

| 服務 | SMTP_HOST | SMTP_PORT | SMTP_USERNAME / SMTP_PASSWORD |
|---|---|---|---|
| Microsoft 365 / Outlook | `smtp.office365.com` | `587` | 信箱帳號／密碼（需管理員開啟 SMTP AUTH） |
| SendGrid | `smtp.sendgrid.net` | `587` | `apikey`／你的 API Key |
| Brevo | `smtp-relay.brevo.com` | `587` | 後台顯示的登入帳號／SMTP 金鑰 |
| 使用 SSL 465 埠的主機 | 主機位址 | `465` | 帳號／密碼（系統會自動改用 SSL） |

## 怎麼確認有寄出

1. 建立一份合約，簽署方填你自己的另一個信箱，按「發送簽署邀請」。
2. 管理台每一方會顯示 **Email：已寄出**。若顯示 **寄送失敗**，連結仍可複製轉交，請檢查帳號密碼。
3. 查看錯誤原因：<https://console.cloud.google.com/logs/query?project=mycontractapp-911>，搜尋 `SMTP send failed`。

## 注意

- `.env` 含密碼，**不要上傳到 GitHub**（專案的 `.gitignore` 已排除）。
- 收件人沒收到時，請先看垃圾郵件匣。

## 系統會寄哪些信

| 時機 | 收件人 | 內容 |
|---|---|---|
| 管理者按「發送簽署邀請」 | 每一方（2 或 3 位） | 各自專屬的一次性簽署連結＋期限 |
| 催簽提醒 | 尚未簽署的人 | 再次附上簽署連結 |
| **最後一方簽完（合約全部簽署完成）** | 每一方＋`COMPLETION_CC` 名單 | 「【已完成簽署】合約編號 名稱」：各方公司資料、完成時間、PDF 的 SHA-256 雜湊值；**附上已簽署 PDF**（超過 10 MB 改附下載連結）；另附該收件人的下載連結，之後可重新下載 |

### 完成通知的選用設定

```env
# 完成時另外寄一份副本（例如你自己或法務），多個用逗號分隔
COMPLETION_CC=sam@example.com,legal@example.com
```

- 同一份合約只會**自動寄一次**（以資料庫交易防止重複寄送）。
- 寄信失敗不影響簽署結果。管理台和合約內容頁會顯示「完成通知：已寄給 N 位／成功 x／失敗 y」，並有「**重寄完成通知**」按鈕。
- 公司內部的轉信伺服器若不加密，可設 `SMTP_SECURE=none`。
