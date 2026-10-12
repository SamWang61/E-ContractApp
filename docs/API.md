# API Contract／API 契約

Base path／基底路徑: `/api`

## Create invitations／建立邀請

`POST /signature/invite` requires a Firebase ID token and contract-owner authorization.／需要 Firebase ID Token 並通過合約擁有者授權。

```json
{
  "tenantId": "tenant-001",
  "contractId": "contract-001",
  "expiresAt": "2026-12-31T16:00:00Z",
  "signers": [
    {"id": "signer-a", "role": "甲方", "email": "a@example.com"},
    {"id": "signer-b", "role": "乙方", "email": "b@example.com"}
  ]
}
```

## Read invitation／讀取邀請

`GET /signature/invite?token={rawToken}` returns only the signer role, email, expiration, and contract summary.／只回傳簽署角色、Email、期限與合約摘要。

## Consume invitation／消耗邀請

`POST /signature/action` accepts `sign`, `decline`, or `request_changes`.／接受三種動作。

```json
{"token":"...","action":"sign","name":"Alex","consent":true,"reason":""}
```

`sign` requires name and consent. `decline` and `request_changes` require a reason.／簽署需姓名與同意；拒絕及退回修改需填原因。

## Reminders／提醒

`POST /signature/reminders` requires manager authorization. It resends the original link for pending invitations due within 48 hours and marks expired invitations as `expired`.／需管理者授權；會重寄兩日內到期的原連結，並將逾期邀請標記為 `expired`。
