# MyContractApp (mycontractapp-911) 診斷筆記 — 2026-10-16

- Hosting: https://mycontractapp-911.web.app （index.html + app.js + styles.css；/sign/<token> 由 app.js 處理）
- Firebase config: https://mycontractapp-911.web.app/__/firebase/init.json （存於 /tmp/fbinit.json；projectId mycontractapp-911）
- API: https://mycontractapp-911.web.app/api/* ，/api/health -> {"ok":true,"service":"mycontractapp-api","region":"asia-east1"}
  - 直接網址 https://asia-east1-mycontractapp-911.cloudfunctions.net/api/health -> 200
  - CORS：反射 Origin，允許 authorization, content-type；GET/OPTIONS/POST
  - POST /api/signature/invite 需 Bearer ID Token；合約須存在且 createdBy==uid，否則 403 owner_required
  - GET /api/signature/invite?token= ；POST /api/signature/action {token,action,name,reason,consent}；POST /api/signature/reminders 需登入
  - 無建立合約 API（/api/contracts 等 404）
- Firestore 索引 signatureInvites.tokenHash（集合組）已由使用者建立並生效（07:22）
- Firebase Auth：07:53 前未啟用（CONFIGURATION_NOT_FOUND）；07:57 使用者已啟用匿名登入，signUp 200
- Firestore 規則：匿名使用者 REST 建立 tenants/demo-tenant/contracts/{id} -> 403 PERMISSION_DENIED
- 資料模型（依 GitHub E-ContractApp 版，線上版可能不同）：tenants/{t}/contracts/{c}，子集合 signatureInvites；APP_BASE_URL 用於產生 /sign/<token>；SMTP 未設時 emailStatus=preview 並回傳 previewUrl（APP_ENV!=production）
- 永久示範站（Manus）：https://esigndemo-922o2gqm.manus.space ，專案目錄 /home/ubuntu/esigndemo
- 使用者需求更新：兩方或三方都要能簽（不是只有三方）
