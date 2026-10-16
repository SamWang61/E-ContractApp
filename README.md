# E-ContractApp

> **使用說明手冊**：[firebase/docs/USER_MANUAL.md](firebase/docs/USER_MANUAL.md)（[PDF 版](firebase/docs/USER_MANUAL.pdf)）

> 全球化合約管理系統／Global Contract Management System

E-ContractApp provides a secure, multi-party contract-signing workflow with email invitations, per-signer links, one-time tokens, expiry governance, reminders, rejection, and change requests.

E-ContractApp 提供安全的多方合約簽署流程，包含 Email 邀請、每方專屬連結、一次性 Token、簽署期限、到期提醒、拒絕簽署與退回修改。

## Current version／目前版本（2026-10-16d）

**`firebase/` is the production project deployed at <https://mycontractapp-911.web.app>.**
**`firebase/` 是目前正式上線的完整專案**（Firebase 專案 `mycontractapp-911`），與 [MyContractApp-eSign](https://github.com/SamWang61/MyContractApp-eSign) 的 `firebase/` 相同。`full/` 保留為早期版本。

| 功能 | 說明 |
|---|---|
| 兩方／三方簽署 | 簽署、退回修改、拒絕（需填原因）；一次性專屬連結 |
| 文件上傳 | PDF／DOCX／TXT，擷取文字與 SHA-256 |
| 翻譯 | 繁體／簡體／英文 |
| 封面 | 起約方從 6 款封面中選擇 |
| 合約編號 | `C-YYMM001`，可修改、不可重複、可查詢 |
| 合約清單與內容頁 | `/contracts`、`/contracts/<編號>` |
| 簽署方公司資料 | 公司名稱、統一編號（檢查碼驗證）、地址、代表人 |
| 已簽署 PDF | 封面、條款、立約當事人、手寫簽名、稽核紀錄 |
| Email | 邀請信、催簽、**完成後自動寄給各方並附 PDF** |
| 安全規則 | 網頁前端不能直接讀寫資料庫，所有存取經後端 API 驗證 |

**Deploy／部署（Windows）**：雙擊 `firebase\deploy.cmd`（第一次使用前，請依 `firebase/docs/EMAIL_SETUP.md` 設定 `firebase/functions/.env`）。
變更紀錄見 [CHANGELOG.md](CHANGELOG.md)；Manus 示範站原始碼在 `demo/`。

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
firebase/          Production project (hosting + functions + rules + deploy script)／正式版完整專案
demo/              Manus demo site (front-end only)／Manus 示範站
full/functions/    Early version: Python API and token state machine／早期版本後端
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
