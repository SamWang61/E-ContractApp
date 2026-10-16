# MyContractApp（mycontractapp-911）Firebase 端修正說明

> 目前的正式流程已可在 **https://esigndemo-922o2gqm.manus.space/live.html** 執行（連線你的 Firebase 正式後端，不需改任何 Firebase 設定）。
> 以下兩項是 Firebase 端本身的缺陷，下次你從本機部署 Firebase 時一併修正，`mycontractapp-911.web.app` 自己的簽署頁才會正常。

## 已確認的根本原因（2026-10-16 實測）

| # | 問題 | 影響 | 狀態 |
|---|---|---|---|
| 1 | Firebase Authentication 從未啟用（`CONFIGURATION_NOT_FOUND`） | 沒人拿得到 ID Token，「寄送邀請」必定失敗 | 已解決（你已啟用匿名登入） |
| 2 | 前端未依現有規則建立「租戶 → Owner 成員 → 合約」 | 建立合約被拒（`PERMISSION_DENIED`）、寄邀請回 `owner_required` | 已解決（新管理台照現有規則運作，規則一行未改） |
| 3 | `index.html` 以相對路徑載入 `app.js`／`styles.css` | 在 `/sign/<token>` 底下會抓到 `/sign/app.js`（回傳 HTML），**簽署頁從未正常運作** | 待 Firebase 重新部署（暫由 Manus 站 `sign.html` 取代） |
| 4 | 後端 `next_contract_status` 不保留「拒絕／退回」 | 有人拒絕後，其他人仍可簽，合約狀態被蓋回 `partially_signed` | 待後端重新部署（管理台已改為依各方結果顯示） |

## 修正 3：index.html（前端）

把資源路徑改為根目錄絕對路徑：

```html
<link rel="stylesheet" href="/styles.css">
<script type="module" src="/app.js"></script>
```

## 修正 4：functions/main.py（後端）

在 `consume(transaction)` 內、更新合約之前，加入「合約已終止就不再接受簽署」與「保留終止狀態」：

```python
contract_status = contract.get("status")
if contract_status in {"declined", "changes_requested", "fully_signed"}:
    raise ValueError("contract_closed")  # 合約已終止或完成，不再接受新的簽署動作
```

並將 `next_contract_status` 呼叫維持不變（終止狀態已在上方攔截）。前端 `sign.js` 若收到 `contract_closed`，會顯示「此合約已結案或已被拒絕／退回，無法再簽署」。

## 部署指令（在你本機專案資料夾）

```bash
firebase deploy --only hosting,functions --project mycontractapp-911
```

## 上線前建議

- 匿名登入方便示範，但任何拿到網址的人都能建立自己的工作區與合約。正式上線前建議改為 Email／Google 登入。
- 目前後端未設定 SMTP，邀請以「連結」形式回傳（`emailStatus: preview`）。若要真的寄信，於 Functions 環境設定 `SMTP_HOST`、`SMTP_PORT`、`SMTP_USERNAME`、`SMTP_PASSWORD`、`SMTP_FROM`，並確認 `APP_BASE_URL`。
- 手寫簽名目前只在簽署頁作為必要步驟，後端只記錄姓名、同意與時間；若要保存簽名圖檔，需要在後端新增欄位或改存 Storage。
