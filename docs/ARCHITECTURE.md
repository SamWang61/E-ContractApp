# Architecture／系統架構

## Overview／總覽

The signing system uses Firebase Hosting for the web surface, Firebase Python Functions for trusted workflow decisions, Firestore for tenant-scoped state, SMTP for email delivery, and Cloud Scheduler for reminders.

簽署系統使用 Firebase Hosting 提供網頁介面、Firebase Python Functions 執行受信任流程決策、Firestore 保存租戶範圍資料、SMTP 寄送 Email，並由 Cloud Scheduler 執行提醒。

## Layers／分層

1. **Web／前端**: `full/web/` provides the manager invitation form and public `/sign/{token}` experience.／`full/web/` 提供管理者邀請表單與公開簽署頁。
2. **API／後端**: `full/functions/main.py` validates authentication, loads invitations, and executes transitions.／`full/functions/main.py` 驗證身分、載入邀請並執行狀態轉移。
3. **Security primitives／安全核心**: `full/functions/signature_service.py` owns token issuance, expiry checks, and allowed actions.／該模組負責 Token 產生、期限檢查與允許動作。
4. **Persistence／資料層**: invitation documents live below `tenants/{tenantId}/contracts/{contractId}/signatureInvites/{signerId}`.／邀請資料位於租戶與合約的子集合下。
5. **Operations／維運**: `POST /api/signature/reminders` is called by Cloud Scheduler.／Cloud Scheduler 呼叫提醒端點。

## Design rule／設計原則

The browser never decides signer identity, contract ownership, or whether an invitation is still usable. The server is the source of truth.

瀏覽器不得決定簽署人身分、合約擁有權或邀請是否仍可使用；後端才是唯一真實來源。
