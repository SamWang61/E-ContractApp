# 部署到 Firebase｜方法與步驟

> 適用版本：2026-10-16d　｜　正式網址：<https://mycontractapp-911.web.app>
> 部署方式：在 Windows 電腦上雙擊 `firebase\deploy.cmd`，一鍵部署網站、後端 API 和安全規則
> 另一種部署方式（Render + Docker）請見 [DEPLOY_RENDER.md](DEPLOY_RENDER.md)

---

## 1. 架構

| 元件 | Firebase 服務 | 內容 |
|---|---|---|
| 網站 | Firebase Hosting | `firebase/public`（管理台、簽署頁、合約清單） |
| 後端 API | Cloud Functions（Python 3.12，`asia-east1`） | `firebase/functions/main.py`，網址 `/api/*` 由 Hosting 轉給函式 `api` |
| 資料庫 | Cloud Firestore | 合約、簽署邀請、稽核紀錄 |
| 檔案 | Cloud Storage | 上傳的合約文件、手寫簽名、已簽署 PDF |
| 登入 | Firebase Authentication（匿名） | 辨識起約方，不需要註冊 |
| 安全規則 | `firestore.rules`、`storage.rules` | 前端一律不能直接讀寫，只能透過後端 API |

---

## 2. 一次性準備（只要做一次，已完成的可以跳過）

| # | 項目 | 做法 | 目前狀態 |
|---|---|---|---|
| 1 | Blaze 方案 | Firebase 主控台 → 左下角「升級」→ 選 Blaze（隨用隨付）。Cloud Functions 需要這個方案 | 已完成 |
| 2 | 匿名登入 | [Authentication → 登入方式](https://console.firebase.google.com/project/mycontractapp-911/authentication/providers) → 新增「匿名」→ 啟用 | 已完成 |
| 3 | Firestore | [Firestore](https://console.firebase.google.com/project/mycontractapp-911/firestore) → 建立資料庫，位置選 `asia-east1` | 已完成 |
| 4 | Firestore 索引 | 第一次查詢時，錯誤訊息裡會附上建立連結，點開後按「建立」即可（`signatureInvites.tokenHash`） | 已完成 |
| 5 | Storage | [Storage](https://console.firebase.google.com/project/mycontractapp-911/storage) →「開始使用」→ 位置選 `asia-east1` | 已完成 |
| 6 | 翻譯 API（翻成英文時才需要） | [啟用 Cloud Translation API](https://console.cloud.google.com/apis/library/translate.googleapis.com?project=mycontractapp-911)。繁簡互轉不需要 | 依需求 |

**電腦需要安裝的工具**

| 工具 | 版本 | 安裝方式 |
|---|---|---|
| Node.js | 18 以上（已安裝 v24） | <https://nodejs.org> |
| Firebase CLI | 13 以上（已安裝 15.32） | 命令提示字元執行 `npm install -g firebase-tools` |
| Python | 3.12（3.11 / 3.13 也可以） | <https://www.python.org/downloads/>，安裝時勾選「Add python.exe to PATH」 |

---

## 3. 設定 `functions\.env`

這個檔案存放金鑰和寄信密碼，**只留在你的電腦上，不會上傳到 GitHub**。部署腳本第一次執行時，會自動找到舊的簽署金鑰並建立這個檔案。之後如果要調整寄信設定，再手動修改即可。

檔案位置：`C:\Users\USER\iCloudDrive\MyContractApp-eSign-main\firebase\functions\.env`

```env
# 必要：簽署連結加密金鑰（部署腳本會自動保留；請勿更改，否則已發出的連結無法提醒或下載）
SIGNING_TOKEN_ENCRYPTION_KEY=……

# 簽署連結與 Email 裡的網址
APP_BASE_URL=https://mycontractapp-911.web.app

# 寄信（以 Gmail 為例；密碼請用 Google「應用程式密碼」）
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=你的帳號@gmail.com
SMTP_PASSWORD=16 碼應用程式密碼
SMTP_FROM=你的帳號@gmail.com

# 選填：合約完成時的副本收件人，多個用逗號分隔
COMPLETION_CC=

# 選填：公司內部不加密的轉信伺服器才需要
# SMTP_SECURE=none
```

Gmail 應用程式密碼的申請方式見 [EMAIL_SETUP.md](EMAIL_SETUP.md)。

---

## 4. 部署步驟（一鍵）

1. 到 GitHub 下載最新版：[MyContractApp-eSign](https://github.com/SamWang61/MyContractApp-eSign) 或 [E-ContractApp](https://github.com/SamWang61/E-ContractApp) → **Code → Download ZIP**。兩個 repo 的 `firebase/` 內容相同。
2. 解壓後，**覆蓋**到 `C:\Users\USER\iCloudDrive\MyContractApp-eSign-main`。ZIP 裡沒有 `.env`，你原本的金鑰會保留。
3. 進入 `firebase` 資料夾，**雙擊 `deploy.cmd`**。
4. 腳本會依序執行 7 個步驟，看到綠色 `OK` 代表該步驟成功：

| 步驟 | 畫面文字 | 做什麼 | 時間 |
|---|---|---|---|
| 1/7 | Checking Node.js and Firebase CLI | 檢查工具 | 數秒 |
| 2/7 | Finding Python | 找到 Python 3.12 | 數秒 |
| 3/7 | Preparing functions\venv | 建立虛擬環境並安裝後端套件 | 第一次 1–3 分鐘 |
| 4/7 | Preparing functions\.env | 保留或建立金鑰設定 | 數秒 |
| 5/7 | Checking Firebase login | 沒登入時會打開瀏覽器，用 Google 帳號登入 | 數秒 |
| 6/7 | Deploying API + website + Firestore security rules | 部署後端、網站、安全規則，以及 Storage 規則 | 3–6 分鐘 |
| 7/7 | Verifying the live site | 呼叫 `/api/health` 確認版本 | 數秒 |

5. 如果出現 **「Would you like to proceed with deletion?」**，代表雲端有舊的函式不在這次部署裡，請回答 **N**。
6. 最後看到 **`API is live ... 2026-10-16d`** 就是成功。打開網站後按 **Ctrl + F5** 強制重新整理。

---

## 5. 手動指令（進階）

在 `firebase` 資料夾開啟命令提示字元執行：

| 目的 | 指令 | 時間 |
|---|---|---|
| 登入 Firebase | `firebase login` | — |
| 全部部署 | `firebase deploy --project mycontractapp-911` | 3–6 分鐘 |
| 只改網頁（HTML/CSS/JS、頁尾） | `firebase deploy --only hosting --project mycontractapp-911` | 約 30 秒 |
| 只改後端 | `firebase deploy --only functions --project mycontractapp-911` | 2–5 分鐘 |
| 只改安全規則 | `firebase deploy --only firestore:rules,storage --project mycontractapp-911` | 約 20 秒 |
| 查看後端日誌 | `firebase functions:log --project mycontractapp-911` | — |

> 手動部署後端前，請確認 `functions\venv` 存在，否則 Firebase CLI 無法分析 Python 程式。第一次請先執行一次 `deploy.cmd`。

---

## 6. 部署後驗證

| 檢查 | 方法 | 正確結果 |
|---|---|---|
| 後端版本 | 打開 <https://mycontractapp-911.web.app/api/health> | `{"ok": true, ..., "version": "2026-10-16d"}` |
| 管理台 | 打開首頁 | 看得到 STEP 1–5，頁尾有「X Shop AI Labs.」連結 |
| 合約清單 | 打開 `/contracts` | 列出這個瀏覽器建立的合約 |
| 完整流程 | 建立一份兩方合約，簽署人填你自己的兩個信箱 → 發送邀請 → 兩個連結各簽一次 | 狀態變成「已全數簽署」，兩個信箱都收到「【已完成簽署】」並附上 PDF |

---

## 7. 回復到上一版

| 元件 | 做法 |
|---|---|
| 網站 | [Hosting 主控台](https://console.firebase.google.com/project/mycontractapp-911/hosting) → 版本記錄 → 在舊版本按「⋮」→「回復」，立即生效 |
| 後端 | 從 GitHub 下載舊版 commit 的 ZIP（repo → Commits → 選版本 → Browse files → Code → Download ZIP），覆蓋後重新執行 `deploy.cmd` |

---

## 8. 常見問題

| 狀況 | 原因 | 解決方式 |
|---|---|---|
| 第 4 步出現「拒絕存取路徑 …\.env」 | 舊版腳本會掃到受保護的資料夾 | 已在新版修正，請下載最新版 |
| `Python 3.12 not found` | 沒安裝，或沒加入 PATH | 安裝 Python 3.12，並勾選「Add to PATH」 |
| 第 6 步出現 `Failed to load function definition` | 套件沒裝好 | 刪除 `functions\venv` 後重新執行 `deploy.cmd` |
| `Storage rules not deployed` | Storage 還沒「開始使用」 | 照第 2 章第 5 項啟用後，執行 `firebase deploy --only storage` |
| 網站還是舊畫面 | 瀏覽器快取 | 按 Ctrl + F5 |
| `/api/health` 的版本不對 | 後端沒有部署成功 | 檢查第 6 步的紅字，把錯誤訊息複製下來詢問 |
| 翻成英文失敗 | Translation API 沒啟用 | 照第 2 章第 6 項啟用 |
| 沒收到 Email | `.env` 的 SMTP 沒設定或密碼錯誤 | 見 [EMAIL_SETUP.md](EMAIL_SETUP.md)，改完重新部署 |

---

## 9. 費用參考

Blaze 方案有免費額度：Cloud Functions 每月 200 萬次呼叫、Firestore 每天 5 萬次讀取、Storage 5 GB 等，一般中小型的簽約量通常不會超過。建議在 [Google Cloud 帳單](https://console.cloud.google.com/billing) 設定**預算提醒**（例如每月 USD 5），避免意外產生費用。英文翻譯依 Cloud Translation 計費，每月前 50 萬字元免費。

*X Shop AI Labs.｜<https://xsh0p.ai>*
