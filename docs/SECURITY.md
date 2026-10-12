# Security／安全設計

## Token handling／Token 處理

- Generate at least 48 bytes of cryptographic randomness.／至少使用 48 bytes 加密級亂數。
- Store a SHA-256 lookup hash; never store raw tokens.／保存 SHA-256 查找雜湊，絕不保存明碼 Token。
- Store ciphertext only when reminder resend is required, protected by `SIGNING_TOKEN_ENCRYPTION_KEY`.／只有提醒重寄需要保存密文，並由 `SIGNING_TOKEN_ENCRYPTION_KEY` 保護。
- Enforce expiration on every read and action.／每次讀取與操作都檢查期限。

## Atomicity／原子性

The invitation status and contract status update must occur in one Firestore transaction. This prevents two concurrent requests from both signing the same invitation.

邀請狀態與合約狀態必須在同一個 Firestore 交易中更新，避免兩個並發請求同時消耗同一邀請。

## Secrets／密鑰

SMTP credentials and encryption keys belong in Secret Manager or deployment secrets, never in Git.／SMTP 憑證與加密金鑰應放在 Secret Manager 或部署密鑰中，絕不可進 Git。
