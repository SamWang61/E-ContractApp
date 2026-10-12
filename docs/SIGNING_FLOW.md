# Signing Flow／簽署流程

## Happy path／正常簽署

1. Manager selects a contract, signer role, email, and expiration.／管理者選擇合約、簽署角色、Email 與期限。
2. The API issues a random URL-safe token and stores its SHA-256 hash plus encrypted ciphertext.／API 產生 URL-safe 隨機 Token，保存 SHA-256 雜湊與加密密文。
3. SMTP sends one private URL per signer.／SMTP 為每位簽署人寄送專屬私密連結。
4. The signer opens the link and the API resolves the hash without exposing the token in Firestore.／簽署人開啟連結，API 以雜湊定位邀請，Firestore 不保存明碼 Token。
5. A successful sign consumes the invitation in a transaction and updates the contract.／簽署成功後由交易一次性消耗邀請並更新合約。

## Alternate decisions／替代決策

- `decline`: requires a reason, records the decision, and moves the contract to owner review.／`decline` 必須填原因，記錄決定並進入管理者複審。
- `request_changes`: requires a reason, records the requested changes, and moves the contract to owner review.／`request_changes` 必須填原因，記錄修改要求並進入管理者複審。
- Any terminal invitation state rejects all later actions.／邀請一旦進入終止狀態，後續操作一律拒絕。

## State model／狀態模型

```text
pending -> signed -> (partially_signed | fully_signed)
        -> declined -> needs_owner_review
        -> changes_requested -> needs_owner_review
        -> expired
```
