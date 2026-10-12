# E-ContractApp

> 全球化合約管理系統／Global Contract Management System

E-ContractApp provides a secure, multi-party contract-signing workflow with email invitations, per-signer links, one-time tokens, expiry governance, reminders, rejection, and change requests.

E-ContractApp 提供安全的多方合約簽署流程，包含 Email 邀請、每方專屬連結、一次性 Token、簽署期限、到期提醒、拒絕簽署與退回修改。

## Features／功能

- Per-signer invitation URL and one-time token／每位簽署人獨立連結與一次性 Token
- SHA-256 lookup hash plus encrypted ciphertext for reminder resend／保存 SHA-256 雜湊與加密密文，提醒時重寄原連結
- Atomic consume transaction prevents replay／原子交易消耗 Token，防止重放
- `sign`, `decline`, and `request_changes` workflow／支援簽署、拒絕與退回修改
- Expiry enforcement and scheduled reminders／期限驗證與排程提醒
- Firebase Functions + Firestore + SMTP／Firebase Functions、Firestore 與 SMTP 架構
- Chinese and English documentation／完整中英文文件

## Repository layout／目錄結構

```text
full/functions/    Firebase Python API and token state machine／後端 API 與 Token 狀態機
full/web/          Lightweight invitation and signing UI／前端邀請與公開簽署頁
docs/              Bilingual architecture, API and security docs／雙語架構、API、安全文件
tests/             Unit tests／單元測試
.github/workflows/ Continuous integration／持續整合檢查
```

## Quick start／快速開始

```bash
cd full/functions
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
pip install pytest
pytest -q
```

Set production secrets through Secret Manager or the deployment environment. Never commit SMTP credentials or `SIGNING_TOKEN_ENCRYPTION_KEY`.

正式環境請透過 Secret Manager 或部署環境設定密鑰，絕不要提交 SMTP 密碼或 `SIGNING_TOKEN_ENCRYPTION_KEY`。

## API／介面

- `POST /api/signature/invite` — manager creates invitations／管理者建立邀請
- `GET /api/signature/invite?token=...` — public invitation lookup／公開讀取邀請
- `POST /api/signature/action` — sign, decline, or request changes／簽署、拒絕或退回修改
- `POST /api/signature/reminders` — send due reminders／執行到期提醒

See [docs/API.md](docs/API.md) for request and response examples.／請參閱 [docs/API.md](docs/API.md) 的中英文範例。

## License／授權

See [LICENSE](LICENSE).
