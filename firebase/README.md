# MyContractApp：Firebase 正式版（可直接部署）

> **使用說明手冊**：[docs/USER_MANUAL.md](docs/USER_MANUAL.md)（[PDF 版](docs/USER_MANUAL.pdf)）

> **部署文件**：[部署到 Firebase](docs/DEPLOY_FIREBASE.md)（[PDF](docs/DEPLOY_FIREBASE.pdf)）｜[部署到 Render（Docker）](docs/DEPLOY_RENDER.md)（[PDF](docs/DEPLOY_RENDER.pdf)）

已在 Firebase 官方模擬器驗證：API 流程 **27/27 通過**，瀏覽器單輪實測通過（封面、上傳、翻譯、手寫簽名、一次性連結、進度更新）。

## 新功能
| 功能 | 說明 |
|---|---|
| 1. 上傳文件 | PDF / Word(.docx) / TXT / PNG / JPG，10 MB 內；存放於 Firebase Storage（僅後端可讀），自動擷取文字供翻譯與簽署頁顯示。發出邀請後文件鎖定。 |
| 2. 合約翻譯 | 繁體 / 简体 / English 三語切換。繁↔簡用 OpenCC（免費、即時）；中↔英用 Google Cloud Translation API。翻譯結果快取，原文變更才重譯。 |
| 3. 封面選擇 | 起約方從 6 款封面擇一（經典藏青、商務黑金、極簡白、科技藍、典雅玉綠、朱印契約），管理台與簽署頁同步顯示。 |

## 2026-10-16 第二版新增
| 功能 | 說明 |
|---|---|
| 合約編號 | 預設 `C-YYMM001`（台灣時間年月，每月重新從 001 起算）；建立時可改、建立後也可在合約內容頁修改；同一帳號內不可重複（不分大小寫）；手動用掉的號碼，預設會自動跳過 |
| 瀏覽所有合約 | `/contracts`：列出這個帳號的所有合約，可用編號、名稱、摘要、簽署方 Email 查詢，並依狀態篩選 |
| 合約內容頁 | `/contracts/<合約編號>`：封面、條款、附件、三語翻譯、各方簽署進度、待簽連結（可隨時找回）、下載已簽署 PDF |
| 下載已簽署 PDF | 全部簽完後，管理者與簽署人都可下載：封面＋條款＋附件＋各方手寫簽名＋稽核紀錄；上傳的原始 PDF 會附在最後 |
| 簽署方公司資料 | 每一方新增「公司名稱／統一編號／公司地址／代表人」（選填，個人簽約可留白）；台灣統編 8 碼依財政部檢查碼驗證，外國公司可填 1–20 碼英數字；顯示於封面、簽署頁、管理台、合約內容頁與已簽署 PDF（立約當事人頁＋簽署頁）；可用公司名稱、統編、代表人查詢 |
| 合約完成自動通知 | 最後一方簽完後，自動寄「【已完成簽署】」給每一方（＋`COMPLETION_CC`），附已簽署 PDF；只寄一次，可手動重寄；管理台顯示寄送結果 |
| 自動寄 Email | 見 `docs/EMAIL_SETUP.md` |
| 安全規則 | 前端直接讀寫 Firestore 全部拒絕，見 `docs/SECURITY_RULES.md` |

## 修正的錯誤
1. 簽署連結 `/sign/<token>` 打開是空白／無反應 → 前端改為同一頁面處理，資源全部使用絕對路徑。
2. 前端被 Firestore 規則擋住無法建立合約 → 改由後端 API 建立（含租戶與 Owner 身分），**不需要再改 Firestore 規則**。
3. 有人拒絕或退回後，其他人仍可簽署 → 後端交易中檢查合約狀態，回傳 `contract_closed`。
4. 新版 Firestore 套件交易讀取格式改變，會讓簽署失敗 → 相容新舊版本。
5. 部署分析時 `firestore.client()` 需要憑證而失敗 → 改為延遲連線。
6. 正式環境不回傳簽署連結（未設定寄信時無法轉交）→ 未設定 SMTP 時一律回傳連結給建立者。

## 部署前（一次性，各約 1 分鐘）
1. **啟用 Storage**：<https://console.firebase.google.com/project/mycontractapp-911/storage> →「開始使用」→ 位置選 `asia-east1`。
2. **啟用翻譯（英文才需要）**：<https://console.cloud.google.com/apis/library/translate.googleapis.com?project=mycontractapp-911> →「啟用」。繁簡互轉不需要。

## 部署（只要一次）
1. 在 GitHub 下載此 repo（Code → Download ZIP），解壓到**沒有中文的路徑**，例如 `C:\mca`。
2. 進入 `C:\mca\firebase`，**雙擊 `deploy.cmd`**。
3. 腳本會自動：檢查 Node/Python → 建立 venv 安裝套件 → 沿用你舊專案的簽署金鑰（找不到就新建）→ 登入 Firebase → 部署 API 與網站 → 驗證上線。
4. 若詢問是否刪除其他 functions，請回答 **N**。
5. 任何一步失敗都會停下並顯示 `STOPPED:`，不會部署一半。

## 本機驗證（開發者）
```
firebase emulators:start --only auth,functions,firestore,storage,hosting --project mycontractapp-911
python tests/api_flow_test.py http://127.0.0.1:5055
python tests/ui_smoke_test.py http://127.0.0.1:5055 某個文件.txt
python tests/rules_test.py
python tests/ui_pages_test.py http://127.0.0.1:5055
```
模擬器需要 `functions/.env.local`：`APP_BASE_URL=http://127.0.0.1:5055`、`TRANSLATE_FAKE=1`、`STORAGE_EMULATOR_HOST=http://127.0.0.1:9199`。
