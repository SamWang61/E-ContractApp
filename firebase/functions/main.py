"""MyContractApp API（Cloud Functions for Firebase, Python, asia-east1）。

端點（皆在 /api 之下）：
  GET  /health
  POST /contracts                 建立合約（自動建立租戶與 Owner 身分）        [需登入]
  POST /contracts/document        上傳合約文件（PDF/DOCX/TXT/PNG/JPG，10MB）     [需登入，建立者]
  GET  /contracts/document        下載合約文件                                   [需登入，建立者]
  POST /contracts/translate       翻譯合約內容（zh-TW / zh-CN / en）              [需登入，建立者]
  GET  /contracts/status          合約與各方簽署進度                              [需登入，建立者]
  POST /signature/invite          產生一次性簽署邀請                              [需登入，建立者]
  GET  /signature/invite          以 token 讀取邀請與合約（可帶 lang 翻譯）
  GET  /signature/document        以 token 下載合約文件
  POST /signature/action          簽署／退回修改／拒絕（含手寫簽名圖）
  POST /signature/reminders       逾期標記與催簽提醒                              [需登入]
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
import base64
import hashlib
import os
import re
import secrets
import smtplib
from typing import Any

from cryptography.fernet import Fernet
from firebase_admin import auth, firestore, initialize_app, storage
from firebase_functions import https_fn, options

from documents import decode_signature, decode_upload, extract_text
from pdf_export import build_signed_pdf, digest
from signature_service import contract_closed, issue_token, next_contract_status, token_digest, validate_action
from translation import SUPPORTED, translate_fields

initialize_app()
EMULATOR = os.getenv("FUNCTIONS_EMULATOR") == "true"
PROJECT_ID = os.getenv("GCLOUD_PROJECT") or os.getenv("GOOGLE_CLOUD_PROJECT") or "mycontractapp-911"


class _LazyDB:
    """部署時 Firebase CLI 會載入本模組分析函式定義，當下沒有憑證；
    因此 Firestore 連線延到第一次實際使用才建立。"""
    _client = None

    def __getattr__(self, name):
        if _LazyDB._client is None:
            if EMULATOR:  # 本機模擬器：不需要 Google 憑證
                from google.auth.credentials import AnonymousCredentials
                from google.cloud import firestore as gcf
                _LazyDB._client = gcf.Client(project=PROJECT_ID, credentials=AnonymousCredentials())
            else:
                _LazyDB._client = firestore.client()
        return getattr(_LazyDB._client, name)


DB = _LazyDB()
INVITES = "signatureInvites"
KEY = base64.urlsafe_b64encode(hashlib.sha256(os.getenv("SIGNING_TOKEN_ENCRYPTION_KEY", "development-only-change-me").encode()).digest())
CIPHER = Fernet(KEY)
COVERS = {"classic-navy", "business-gold", "minimal-white", "tech-blue", "jade-green", "crimson-seal"}
MAX_PARTIES = 3


# ---------------------------------------------------------------- helpers
def response(data: Any, status: int = 200):
    return https_fn.Response(__import__("json").dumps(data, ensure_ascii=False, default=str), status=status, mimetype="application/json")


def app_base_url() -> str:
    return os.getenv("APP_BASE_URL", "https://mycontractapp-911.web.app").rstrip("/")


def require_user(req) -> dict:
    header = req.headers.get("Authorization", "")
    if not header.startswith("Bearer "):
        raise PermissionError("authentication_required")
    try:
        return auth.verify_id_token(header[7:].strip())
    except Exception as exc:  # noqa: BLE001
        raise PermissionError("invalid_auth_token") from exc


def bucket():
    name = os.getenv("STORAGE_BUCKET") or None
    if EMULATOR:  # 本機模擬器：不需要 Google 憑證
        from google.auth.credentials import AnonymousCredentials
        from google.cloud import storage as gcs
        return gcs.Client(project=PROJECT_ID, credentials=AnonymousCredentials()).bucket(name or f"{PROJECT_ID}.firebasestorage.app")
    return storage.bucket(name)


def tenant_of(uid: str) -> str:
    return f"t-{uid}"


def contract_ref(tenant_id: str, contract_id: str):
    return DB.collection("tenants").document(tenant_id).collection("contracts").document(contract_id)


def invite_ref(tenant_id: str, contract_id: str, signer_id: str):
    return contract_ref(tenant_id, contract_id).collection(INVITES).document(signer_id)


def owned_contract(user: dict, tenant_id: str, contract_id: str):
    snap = contract_ref(tenant_id, contract_id).get()
    if not snap.exists or (snap.to_dict() or {}).get("createdBy") != user["uid"]:
        raise PermissionError("owner_required")
    return snap


NO_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{1,39}$")
TW_TZ = timezone(timedelta(hours=8))


def number_key(no: str) -> str:
    return no.strip().upper()


def clean_number(no: Any) -> str:
    no = str(no or "").strip()
    if not NO_RE.match(no):
        raise ValueError("invalid_contract_no")
    return no


def month_prefix() -> str:
    return "C-" + datetime.now(TW_TZ).strftime("%y%m")


def peek_next_number(tref) -> str:
    """預設編號 C-YYMM001 起跳，每月重新計數；已被使用（含手動輸入）的號碼自動跳過。"""
    prefix = month_prefix()
    n = int(((tref.collection("counters").document(prefix).get().to_dict()) or {}).get("value", 0))
    while True:
        n += 1
        cand = f"{prefix}{n:03d}"
        if not tref.collection("contractNumbers").document(number_key(cand)).get().exists:
            return cand


def reserve_number(tref, no: str, contract_id: str, release: str | None = None) -> None:
    """在交易中保留編號（同一工作區不可重複），必要時釋放舊編號，並推進當月計數。"""
    key_ref = tref.collection("contractNumbers").document(number_key(no))
    prefix = month_prefix()
    counter_ref = tref.collection("counters").document(prefix)

    @firestore.transactional
    def run(tx):
        taken = tx_get(tx, key_ref)
        if taken and taken.get("contractId") != contract_id:
            raise ValueError("contract_no_taken")
        counter = int(tx_get(tx, counter_ref).get("value", 0))
        m = re.fullmatch(re.escape(prefix) + r"(\d{3,})", number_key(no))
        tx.set(key_ref, {"contractId": contract_id, "contractNo": no, "at": firestore.SERVER_TIMESTAMP})
        if m and int(m.group(1)) > counter:
            tx.set(counter_ref, {"value": int(m.group(1))})
        if release and number_key(release) != number_key(no):
            tx.delete(tref.collection("contractNumbers").document(number_key(release)))

    run(DB.transaction())


def resolve_contract(user: dict, tenant_id: str, contract_id: str = "", contract_no: str = ""):
    """以內部 ID 或合約編號找到自己的合約。"""
    if not contract_id and contract_no:
        hit = DB.collection("tenants").document(tenant_id).collection("contractNumbers").document(number_key(contract_no)).get()
        if not hit.exists:
            raise LookupError("contract_not_found")
        contract_id = (hit.to_dict() or {}).get("contractId", "")
    return owned_contract(user, tenant_id, contract_id)


def valid_tw_ubn(no: str) -> bool:
    """台灣統一編號檢查碼（財政部 2023 新制：加權和可被 5 整除；第 7 碼為 7 時加 1 亦可）。"""
    if not re.fullmatch(r"\d{8}", no):
        return False
    weights = [1, 2, 1, 2, 1, 2, 4, 1]
    total = sum(sum(divmod(int(d) * w, 10)) for d, w in zip(no, weights))
    return total % 5 == 0 or (no[6] == "7" and (total + 1) % 5 == 0)


def clean_company(p: dict) -> dict:
    """簽署方公司資料（選填）。統編若為 8 位數字依台灣檢查碼驗證；外國公司可填 1–20 碼英數字。"""
    tax = str(p.get("taxId", "")).strip().upper().replace(" ", "")
    if tax and (not re.fullmatch(r"[A-Z0-9-]{1,20}", tax) or (re.fullmatch(r"\d{8}", tax) and not valid_tw_ubn(tax))):
        raise ValueError("invalid_tax_id")
    return {"company": str(p.get("company", "")).strip()[:120], "taxId": tax,
            "address": str(p.get("address", "")).strip()[:200], "representative": str(p.get("representative", "")).strip()[:60]}


def tx_get(transaction, ref) -> dict:
    """相容新舊版 google-cloud-firestore：transaction.get 可能回傳快照或產生器。"""
    result = transaction.get(ref)
    if not hasattr(result, "to_dict"):
        result = next(iter(result), None)
    return (result.to_dict() if result is not None else None) or {}


def find_invite(raw: str):
    if not raw:
        raise ValueError("token_required")
    snap = next(DB.collection_group(INVITES).where("tokenHash", "==", token_digest(raw)).limit(1).stream(), None)
    if not snap:
        raise LookupError("invite_not_found")
    return snap


def send_email(to: str, subject: str, text: str, attachments: list[tuple[bytes, str]] | None = None) -> str:
    """回傳 sent / preview（未設定 SMTP）/ failed（SMTP 錯誤，不中斷流程）。attachments: [(PDF bytes, 檔名)]"""
    host = os.getenv("SMTP_HOST")
    if not host:
        return "preview"
    port = int(os.getenv("SMTP_PORT", "587"))
    message = EmailMessage()
    message["From"] = os.getenv("SMTP_FROM") or os.getenv("SMTP_USERNAME") or "no-reply@example.com"
    message["To"] = to
    message["Subject"] = subject
    message.set_content(text)
    for data, filename in attachments or []:
        message.add_attachment(data, maintype="application", subtype="pdf", filename=filename)
    try:
        if port == 465 or os.getenv("SMTP_SECURE", "").lower() == "ssl":
            server = smtplib.SMTP_SSL(host, port, timeout=20)
        else:
            server = smtplib.SMTP(host, port, timeout=20)
            if os.getenv("SMTP_SECURE", "").lower() != "none":  # none：內部轉信伺服器不加密
                server.starttls()
        with server:
            if os.getenv("SMTP_USERNAME"):
                server.login(os.getenv("SMTP_USERNAME"), os.getenv("SMTP_PASSWORD", ""))
            server.send_message(message)
        return "sent"
    except Exception as exc:  # noqa: BLE001
        print(f"SMTP send failed to {to}: {exc}")
        return "failed"


def expiry(value: Any) -> datetime:
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00")) if value else datetime.now(timezone.utc) + timedelta(days=7)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    now = datetime.now(timezone.utc)
    if parsed <= now or parsed > now + timedelta(days=90):
        raise ValueError("expiration_must_be_between_now_and_90_days")
    return parsed


def iso(value: Any) -> str | None:
    return value.isoformat() if isinstance(value, datetime) else (str(value) if value else None)


def content_fields(contract: dict) -> dict[str, str]:
    return {
        "title": contract.get("title", ""),
        "summary": contract.get("summary", ""),
        "body": contract.get("body", ""),
        "documentText": contract.get("documentText", ""),
    }


def translated(ref, contract: dict, lang: str) -> dict[str, str]:
    """翻譯並快取到合約文件 translations.{lang}；原文變更時自動失效。"""
    fields = content_fields(contract)
    digest = hashlib.sha256(repr(sorted(fields.items())).encode()).hexdigest()[:16]
    cached = (contract.get("translations") or {}).get(lang) or {}
    if cached.get("hash") == digest:
        return cached.get("fields", {})
    result = translate_fields(fields, lang)
    ref.set({"translations": {lang: {"hash": digest, "fields": result, "at": firestore.SERVER_TIMESTAMP}}}, merge=True)
    return result


def public_contract(contract_id: str, contract: dict) -> dict:
    doc = contract.get("document") or {}
    return {
        "id": contract_id,
        "contractNo": contract.get("contractNo") or contract_id,
        "title": contract.get("title", ""),
        "summary": contract.get("summary", ""),
        "body": contract.get("body", ""),
        "documentText": contract.get("documentText", ""),
        "coverId": contract.get("coverId", "classic-navy"),
        "language": contract.get("language", "zh-TW"),
        "parties": contract.get("parties", []),
        "status": contract.get("status", "draft"),
        "createdAt": iso(contract.get("createdAt")),
        "document": {"name": doc.get("name"), "type": doc.get("type"), "size": doc.get("size")} if doc else None,
    }


def create_invite(tenant_id: str, contract_id: str, signer: dict, expires_at: datetime, title: str) -> dict:
    email = str(signer.get("email", "")).strip().lower()
    signer_id = str(signer.get("id") or email)
    if "@" not in email or not signer_id:
        raise ValueError("invalid_signer")
    token = issue_token()
    ref = invite_ref(tenant_id, contract_id, signer_id)
    role = str(signer.get("role", "signer"))[:20]
    ref.set({"signerId": signer_id, "email": email, "role": role, "tokenHash": token.digest,
             "tokenCiphertext": CIPHER.encrypt(token.raw.encode()).decode(), "status": "pending",
             "expiresAt": expires_at, "createdAt": firestore.SERVER_TIMESTAMP, "updatedAt": firestore.SERVER_TIMESTAMP,
             "reminderCount": 0})
    url = f"{app_base_url()}/sign/{token.raw}"
    delivery = send_email(email, f"簽署邀請／Signing invitation: {title}",
                          f"請使用專屬連結完成簽署／Use your private signing link:\n{url}\n\n期限／Expires: {expires_at.isoformat()}")
    ref.update({"emailStatus": delivery, "lastSentAt": firestore.SERVER_TIMESTAMP})
    # 連結只回給合約建立者（此端點需登入且必須是建立者），寄信成功與否都可自行轉交
    return {"signerId": signer_id, "email": email, "role": role, "emailStatus": delivery,
            "expiresAt": expires_at.isoformat(), "previewUrl": url}


# ---------------------------------------------------------------- handlers
def h_create_contract(req, payload):
    user = require_user(req)
    uid = user["uid"]
    title = str(payload.get("title", "")).strip()[:120]
    if not title:
        raise ValueError("title_required")
    parties = payload.get("parties") or []
    if not (2 <= len(parties) <= MAX_PARTIES):
        raise ValueError("parties_must_be_2_or_3")
    clean = []
    for i, p in enumerate(parties):
        role = str(p.get("role", "")).strip()[:20] or f"簽署方{i + 1}"
        email = str(p.get("email", "")).strip().lower()
        if "@" not in email:
            raise ValueError("invalid_signer")
        clean.append({"id": f"signer-{i + 1}", "role": role, "email": email, **clean_company(p)})
    cover = str(payload.get("coverId", "classic-navy"))
    if cover not in COVERS:
        cover = "classic-navy"
    lang = str(payload.get("language", "zh-TW"))
    if lang not in SUPPORTED:
        lang = "zh-TW"
    tenant_id = tenant_of(uid)
    tref = DB.collection("tenants").document(tenant_id)
    if not tref.get().exists:
        tref.set({"ownerId": uid, "name": "線上簽約工作區", "createdAt": firestore.SERVER_TIMESTAMP})
    mref = tref.collection("members").document(uid)
    if not mref.get().exists:
        mref.set({"uid": uid, "role": "Owner", "createdAt": firestore.SERVER_TIMESTAMP})
    contract_id = "c-" + datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S") + "-" + secrets.token_hex(3)
    wanted = str(payload.get("contractNo", "")).strip()
    contract_no = clean_number(wanted) if wanted else peek_next_number(tref)
    for _ in range(5):  # 預設編號遇到同時建立時自動取下一號
        try:
            reserve_number(tref, contract_no, contract_id)
            break
        except ValueError:
            if wanted:
                raise
            contract_no = peek_next_number(tref)
    else:
        raise ValueError("contract_no_taken")
    contract_ref(tenant_id, contract_id).set({
        "contractId": contract_id, "contractNo": contract_no, "contractNoKey": number_key(contract_no), "title": title,
        "summary": str(payload.get("summary", "")).strip()[:2000],
        "body": str(payload.get("body", "")).strip()[:60000],
        "coverId": cover, "language": lang, "parties": clean,
        "partyEmails": {p["role"]: p["email"] for p in clean}, "partyCount": len(clean),
        "createdBy": uid, "status": "draft", "signatures": [],
        "createdAt": firestore.SERVER_TIMESTAMP, "updatedAt": firestore.SERVER_TIMESTAMP,
    })
    return response({"ok": True, "tenantId": tenant_id, "contractId": contract_id, "contractNo": contract_no})


def h_next_number(req):
    user = require_user(req)
    return response({"ok": True, "contractNo": peek_next_number(DB.collection("tenants").document(tenant_of(user["uid"])))})


def h_rename(req, payload):
    user = require_user(req)
    tenant_id = tenant_of(user["uid"])
    snap = owned_contract(user, tenant_id, str(payload.get("contractId", "")))
    no = clean_number(payload.get("contractNo"))
    old = (snap.to_dict() or {}).get("contractNo")
    reserve_number(DB.collection("tenants").document(tenant_id), no, snap.id, release=old)
    snap.reference.update({"contractNo": no, "contractNoKey": number_key(no), "updatedAt": firestore.SERVER_TIMESTAMP})
    return response({"ok": True, "contractId": snap.id, "contractNo": no})


def h_list(req):
    """瀏覽／查詢自己的所有合約：q 比對合約編號、名稱、摘要、簽署方 Email／角色；status 篩選狀態。"""
    user = require_user(req)
    tenant_id = tenant_of(user["uid"])
    q = str(req.args.get("q", "")).strip().lower()
    status = str(req.args.get("status", "")).strip()
    rows = []
    for d in DB.collection("tenants").document(tenant_id).collection("contracts").where("createdBy", "==", user["uid"]).stream():
        c = d.to_dict() or {}
        if status and c.get("status") != status:
            continue
        hay = " ".join([str(c.get("contractNo", "")), d.id, c.get("title", ""), c.get("summary", ""),
                        " ".join(f"{p.get('role', '')} {p.get('email', '')} {p.get('company', '')} {p.get('taxId', '')} {p.get('representative', '')}"
                                 for p in c.get("parties", []))]).lower()
        if q and q not in hay:
            continue
        rows.append({"id": d.id, "contractNo": c.get("contractNo") or d.id, "title": c.get("title", ""),
                     "status": c.get("status", "draft"), "coverId": c.get("coverId", "classic-navy"),
                     "partyCount": c.get("partyCount", len(c.get("parties", []))), "signedCount": len(c.get("signatures") or []),
                     "parties": c.get("parties", []), "hasDocument": bool(c.get("document")),
                     "createdAt": iso(c.get("createdAt")), "updatedAt": iso(c.get("updatedAt"))})
    rows.sort(key=lambda r: r.get("createdAt") or "", reverse=True)
    return response({"ok": True, "tenantId": tenant_id, "total": len(rows), "contracts": rows[:500]})


def h_upload_document(req, payload):
    user = require_user(req)
    tenant_id, contract_id = str(payload["tenantId"]), str(payload["contractId"])
    snap = owned_contract(user, tenant_id, contract_id)
    if (snap.to_dict() or {}).get("status") != "draft":
        raise ValueError("document_locked_after_invite")
    name, ctype, data = decode_upload(str(payload.get("fileName", "")), str(payload.get("contentType", "")), str(payload.get("dataBase64", "")))
    path = f"tenants/{tenant_id}/contracts/{contract_id}/document/{name}"
    blob = bucket().blob(path)
    blob.upload_from_string(data, content_type=ctype)
    text = extract_text(ctype, data)
    snap.reference.update({"document": {"name": name, "type": ctype, "size": len(data), "path": path,
                                        "sha256": hashlib.sha256(data).hexdigest()},
                           "documentText": text, "updatedAt": firestore.SERVER_TIMESTAMP})
    return response({"ok": True, "document": {"name": name, "type": ctype, "size": len(data)}, "textLength": len(text)})


def file_response(contract: dict):
    doc = contract.get("document") or {}
    if not doc.get("path"):
        raise LookupError("document_not_found")
    data = bucket().blob(doc["path"]).download_as_bytes()
    from urllib.parse import quote
    return https_fn.Response(data, status=200, mimetype=doc.get("type", "application/octet-stream"),
                             headers={"Content-Disposition": f"inline; filename*=UTF-8''{quote(doc.get('name', 'document'))}",
                                      "Cache-Control": "private, no-store"})


def h_owner_document(req):
    user = require_user(req)
    snap = owned_contract(user, str(req.args.get("tenantId", "")), str(req.args.get("contractId", "")))
    return file_response(snap.to_dict() or {})


def h_translate(req, payload):
    user = require_user(req)
    lang = str(payload.get("lang", ""))
    if lang not in SUPPORTED:
        raise ValueError("unsupported_language")
    snap = owned_contract(user, str(payload["tenantId"]), str(payload["contractId"]))
    return response({"ok": True, "lang": lang, "fields": translated(snap.reference, snap.to_dict() or {}, lang)})


def h_status(req):
    user = require_user(req)
    snap = resolve_contract(user, str(req.args.get("tenantId", "")) or tenant_of(user["uid"]),
                            str(req.args.get("contractId", "")), str(req.args.get("contractNo", "")))
    contract = snap.to_dict() or {}
    invites = []
    for inv in snap.reference.collection(INVITES).stream():
        d = inv.to_dict() or {}
        dec = d.get("decision") or {}
        invites.append({"signerId": d.get("signerId"), "role": d.get("role"), "email": d.get("email"),
                        "status": d.get("status"), "expiresAt": iso(d.get("expiresAt")), "emailStatus": d.get("emailStatus"),
                        "reminderCount": d.get("reminderCount", 0),
                        "link": link_of(d) if d.get("status") == "pending" else None,
                        "decision": {"action": dec.get("action"), "name": dec.get("name"), "reason": dec.get("reason"), "at": iso(dec.get("at"))} if dec else None})
    invites.sort(key=lambda x: x.get("signerId") or "")
    out = public_contract(snap.id, contract)
    notice = contract.get("completionNotice") or {}
    out.update({"completionNotice": {"summary": notice.get("summary"), "at": iso(notice.get("at")), "attached": notice.get("attached")} if notice.get("summary") else None,
                "pendingSigners": contract.get("pendingSigners"), "signedCount": len(contract.get("signatures") or []),
                "tenantId": snap.reference.parent.parent.id})
    return response({"ok": True, "contract": out, "invites": invites})


def link_of(invite: dict) -> str | None:
    try:
        return f"{app_base_url()}/sign/{CIPHER.decrypt(invite['tokenCiphertext'].encode()).decode()}"
    except Exception:  # noqa: BLE001
        return None


def h_create_invites(req, payload):
    user = require_user(req)
    tenant_id, contract_id = str(payload["tenantId"]), str(payload["contractId"])
    snap = owned_contract(user, tenant_id, contract_id)
    contract = snap.to_dict() or {}
    if contract.get("status") not in (None, "draft"):
        raise ValueError("invites_already_sent")
    expires_at = expiry(payload.get("expiresAt"))
    signers = payload.get("signers") or contract.get("parties") or []
    if not (1 <= len(signers) <= MAX_PARTIES):
        raise ValueError("signers_required")
    result = [create_invite(tenant_id, contract_id, s, expires_at, contract.get("title", "合約")) for s in signers]
    snap.reference.set({"status": "invited", "pendingSigners": len(result), "updatedAt": firestore.SERVER_TIMESTAMP}, merge=True)
    return response({"ok": True, "invites": result})


def h_read_invite(req):
    snap = find_invite(str(req.args.get("token", "")))
    invite = snap.to_dict() or {}
    error = validate_action(invite, "sign")
    if error:
        cstatus = (snap.reference.parent.parent.get().to_dict() or {}).get("status")
        return response({"error": error, "status": invite.get("status"), "contractStatus": cstatus,
                         "signedPdfAvailable": invite.get("status") == "signed" and cstatus == "fully_signed"},
                        410 if error == "invite_expired" else 409)
    cref = snap.reference.parent.parent
    contract = cref.get().to_dict() or {}
    if contract_closed(contract):
        return response({"error": "contract_closed", "contractStatus": contract.get("status")}, 409)
    out = public_contract(cref.id, contract)
    lang = str(req.args.get("lang", ""))
    if lang in SUPPORTED and lang != contract.get("language", "zh-TW"):
        out["translation"] = {"lang": lang, "fields": translated(cref, contract, lang)}
    return response({"ok": True, "invite": {"role": invite.get("role"), "email": invite.get("email"), "expiresAt": iso(invite.get("expiresAt"))}, "contract": out})


def h_signer_document(req):
    snap = find_invite(str(req.args.get("token", "")))
    invite = snap.to_dict() or {}
    if invite.get("status") != "pending":
        raise PermissionError("invite_already_consumed")
    return file_response(snap.reference.parent.parent.get().to_dict() or {})


def h_action(req, payload):
    action, raw = str(payload.get("action", "")), str(payload.get("token", ""))
    snap = find_invite(raw)
    name, reason = str(payload.get("name", "")).strip()[:80], str(payload.get("reason", "")).strip()[:500]
    if action == "sign" and (not name or payload.get("consent") is not True):
        raise ValueError("name_and_consent_required")
    if action in {"decline", "request_changes"} and not reason:
        raise ValueError("reason_required")
    signature_png = decode_signature(str(payload.get("signatureImage", ""))) if action == "sign" else None
    if action == "sign" and not signature_png:
        raise ValueError("signature_required")
    invite_now = snap.to_dict() or {}
    signer_id = invite_now.get("signerId", snap.id)
    sig_path = None
    if signature_png:
        cref0 = snap.reference.parent.parent
        tenant_id = cref0.parent.parent.id
        sig_path = f"tenants/{tenant_id}/contracts/{cref0.id}/signatures/{signer_id}.png"
    tx = DB.transaction()

    @firestore.transactional
    def consume(transaction):
        current = tx_get(transaction, snap.reference)
        error = validate_action(current, action)
        if error:
            raise ValueError(error)
        cref = snap.reference.parent.parent
        contract = tx_get(transaction, cref)
        if contract_closed(contract):
            raise ValueError("contract_closed")
        pending = int(contract.get("pendingSigners", 1))
        status = "signed" if action == "sign" else ("declined" if action == "decline" else "changes_requested")
        decision = {"action": action, "name": name, "reason": reason, "at": datetime.now(timezone.utc),
                    "signerId": signer_id, "role": current.get("role"), "signaturePath": sig_path}
        transaction.update(snap.reference, {"status": status, "decision": decision, "consumedAt": firestore.SERVER_TIMESTAMP, "updatedAt": firestore.SERVER_TIMESTAMP})
        update = {"status": next_contract_status(action, pending),
                  "workflowState": "needs_owner_review" if action != "sign" else "active",
                  "updatedAt": firestore.SERVER_TIMESTAMP}
        if action == "sign":
            update["pendingSigners"] = max(0, pending - 1)
            update["signatures"] = firestore.ArrayUnion([decision])
        else:
            update["closedBy"] = {"role": current.get("role"), "name": name, "reason": reason, "action": action}
        transaction.update(cref, update)
        return {"inviteStatus": status, "status": update["status"]}

    result = consume(tx)
    if signature_png and sig_path:
        bucket().blob(sig_path).upload_from_string(signature_png, content_type="image/png")
    if result.get("status") == "fully_signed":
        try:  # 寄信失敗不影響簽署結果；管理台可看到結果並手動重寄
            result["completionNotice"] = notify_completion(snap.reference.parent.parent)
        except Exception as exc:  # noqa: BLE001
            print(f"completion notice failed: {exc}")
            result["completionNotice"] = {"error": "notify_failed"}
    return response({"ok": True, **result})


def signed_pdf_bytes(cref) -> tuple[bytes, str, dict]:
    """回傳（已簽署 PDF、下載檔名、合約資料）；PDF 產生一次後快取在 Storage。"""
    contract = cref.get().to_dict() or {}
    if contract.get("status") != "fully_signed":
        raise ValueError("contract_not_fully_signed")
    cached = contract.get("signedPdf") or {}
    b = bucket()
    data = None
    if cached.get("path"):
        try:
            data = b.blob(cached["path"]).download_as_bytes()
        except Exception:  # noqa: BLE001 - 快取遺失就重新產生
            data = None
    if data is None:
        emails = {(d.to_dict() or {}).get("signerId"): (d.to_dict() or {}).get("email") for d in cref.collection(INVITES).stream()}
        sigs = []
        for dec in sorted(contract.get("signatures") or [], key=lambda d: str(d.get("at"))):
            image = None
            if dec.get("signaturePath"):
                try:
                    image = b.blob(dec["signaturePath"]).download_as_bytes()
                except Exception:  # noqa: BLE001
                    image = None
            sigs.append({**dec, "email": emails.get(dec.get("signerId"), ""), "image": image})
        doc = contract.get("document") or {}
        original = None
        if doc.get("type") == "application/pdf" and doc.get("path"):
            original = b.blob(doc["path"]).download_as_bytes()
        data = build_signed_pdf(contract.get("contractNo") or cref.id, contract, sigs, original)
        tenant_id = cref.parent.parent.id
        path = f"tenants/{tenant_id}/contracts/{cref.id}/signed/{cref.id}-signed.pdf"
        b.blob(path).upload_from_string(data, content_type="application/pdf")
        cref.set({"signedPdf": {"path": path, "sha256": digest(data), "size": len(data), "at": firestore.SERVER_TIMESTAMP}}, merge=True)
    name = f"{contract.get('contractNo') or cref.id}-{contract.get('title', 'contract')}-已簽署.pdf"
    return data, name, contract


MAX_ATTACHMENT = 10 * 1024 * 1024  # 超過 10 MB 改為只附下載連結（多數信箱上限 20–25 MB）


def notify_completion(cref, force: bool = False) -> dict:
    """合約全部簽署完成後，寄「完成通知＋已簽署 PDF」給每一方（以及 COMPLETION_CC 名單）。
    以交易搶旗標，同一份合約只會自動寄一次；force=True 供管理者手動重寄。"""
    tx = DB.transaction()

    @firestore.transactional
    def claim(transaction):
        c = tx_get(transaction, cref)
        if c.get("status") != "fully_signed":
            return False
        if (c.get("completionNotice") or {}).get("claimedAt") and not force:
            return False
        transaction.update(cref, {"completionNotice.claimedAt": firestore.SERVER_TIMESTAMP})
        return True

    if not claim(tx):
        return {"skipped": True}
    data, filename, contract = signed_pdf_bytes(cref)
    no = contract.get("contractNo") or cref.id
    title = contract.get("title", "合約")
    parties = contract.get("parties") or []
    lines = []
    for p in parties:
        extra = "、".join(x for x in [p.get("company", ""), f"統編 {p['taxId']}" if p.get("taxId") else "", f"代表人 {p['representative']}" if p.get("representative") else ""] if x)
        lines.append(f"  ・{p.get('role', '')}：{p.get('email', '')}" + (f"（{extra}）" if extra else ""))
    signed_at = max((str(d.get("at")) for d in contract.get("signatures") or []), default="")
    attach = [(data, filename)] if len(data) <= MAX_ATTACHMENT else []
    sha = digest(data)
    recipients = {}
    for inv in cref.collection(INVITES).stream():
        d = inv.to_dict() or {}
        if d.get("email"):
            recipients[d["email"].lower()] = link_of(d)
    for cc in (os.getenv("COMPLETION_CC") or "").split(","):
        if cc.strip() and "@" in cc:
            recipients.setdefault(cc.strip().lower(), None)
    results = {}
    for email, link in recipients.items():
        text = "\n".join([
            "您好：", "",
            f"合約「{title}」（編號 {no}）已由全部簽署方完成電子簽署。", "",
            "簽署方：", *lines, "",
            f"完成時間：{signed_at[:19]}（UTC）",
            f"已簽署 PDF SHA-256：{sha}", "",
            "已簽署 PDF 已附在本信。" if attach else "PDF 檔案較大，請用下方連結下載。",
            f"隨時重新下載：{link}" if link else "", "",
            "此信由合約管理系統自動寄出，請勿直接回覆。",
        ])
        results[email.replace(".", "\uff0e")] = send_email(email, f"【已完成簽署】{no} {title}", text, attach)
    summary = {"sent": sum(v == "sent" for v in results.values()), "failed": sum(v == "failed" for v in results.values()),
               "preview": sum(v == "preview" for v in results.values()), "total": len(results)}
    cref.set({"completionNotice": {"results": results, "summary": summary, "at": firestore.SERVER_TIMESTAMP,
                                   "attached": bool(attach)}}, merge=True)
    return summary


def h_notify_completion(req, payload):
    user = require_user(req)
    snap = owned_contract(user, str(payload.get("tenantId", "")), str(payload.get("contractId", "")))
    if (snap.to_dict() or {}).get("status") != "fully_signed":
        raise ValueError("contract_not_fully_signed")
    return response({"ok": True, "notice": notify_completion(snap.reference, force=True)})


def signed_pdf_response(cref):
    from urllib.parse import quote
    data, name, _ = signed_pdf_bytes(cref)
    return https_fn.Response(data, status=200, mimetype="application/pdf",
                             headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(name)}",
                                      "Cache-Control": "private, no-store"})


def h_owner_signed_pdf(req):
    user = require_user(req)
    snap = owned_contract(user, str(req.args.get("tenantId", "")), str(req.args.get("contractId", "")))
    return signed_pdf_response(snap.reference)


def h_signer_signed_pdf(req):
    snap = find_invite(str(req.args.get("token", "")))
    if (snap.to_dict() or {}).get("status") != "signed":
        raise PermissionError("signer_only")
    return signed_pdf_response(snap.reference.parent.parent)


def h_reminders(req):
    require_user(req)
    now, sent = datetime.now(timezone.utc), 0
    for snap in DB.collection_group(INVITES).where("status", "==", "pending").stream():
        invite = snap.to_dict() or {}
        expires_at = invite.get("expiresAt")
        if not isinstance(expires_at, datetime):
            continue
        if expires_at <= now:
            snap.reference.update({"status": "expired", "updatedAt": firestore.SERVER_TIMESTAMP})
        elif expires_at - now <= timedelta(days=2):
            raw = CIPHER.decrypt(invite["tokenCiphertext"].encode()).decode()
            title = (snap.reference.parent.parent.get().to_dict() or {}).get("title", "合約")
            send_email(invite["email"], f"提醒簽署／Signing reminder: {title}", f"原專屬連結／Original private link: {app_base_url()}/sign/{raw}")
            snap.reference.update({"reminderCount": firestore.Increment(1), "lastReminderAt": firestore.SERVER_TIMESTAMP})
            sent += 1
    return response({"ok": True, "remindersSent": sent})


# ---------------------------------------------------------------- router
@https_fn.on_request(region="asia-east1", memory=options.MemoryOption.MB_512, timeout_sec=120,
                     cors=options.CorsOptions(cors_origins="*", cors_methods=["get", "post", "options"]))
def api(req: https_fn.Request):
    path = req.path.rstrip("/")
    if req.method == "OPTIONS":
        return response({"ok": True})
    if req.method == "GET" and path.endswith("/health"):
        return response({"ok": True, "service": "mycontractapp-api", "region": "asia-east1", "version": "2026-10-16d"})
    try:
        payload = req.get_json(silent=True) or {}
        m = req.method
        if m == "POST" and path.endswith("/contracts/document"):
            return h_upload_document(req, payload)
        if m == "GET" and path.endswith("/contracts/document"):
            return h_owner_document(req)
        if m == "GET" and path.endswith("/contracts/next-number"):
            return h_next_number(req)
        if m == "GET" and path.endswith("/contracts/list"):
            return h_list(req)
        if m == "POST" and path.endswith("/contracts/number"):
            return h_rename(req, payload)
        if m == "POST" and path.endswith("/contracts/notify-completion"):
            return h_notify_completion(req, payload)
        if m == "GET" and path.endswith("/contracts/signed-pdf"):
            return h_owner_signed_pdf(req)
        if m == "GET" and path.endswith("/signature/signed-pdf"):
            return h_signer_signed_pdf(req)
        if m == "POST" and path.endswith("/contracts/translate"):
            return h_translate(req, payload)
        if m == "GET" and path.endswith("/contracts/status"):
            return h_status(req)
        if m == "POST" and path.endswith("/contracts"):
            return h_create_contract(req, payload)
        if m == "POST" and path.endswith("/signature/invite"):
            return h_create_invites(req, payload)
        if m == "GET" and path.endswith("/signature/invite"):
            return h_read_invite(req)
        if m == "GET" and path.endswith("/signature/document"):
            return h_signer_document(req)
        if m == "POST" and path.endswith("/signature/action"):
            return h_action(req, payload)
        if m == "POST" and path.endswith("/signature/reminders"):
            return h_reminders(req)
        return response({"error": "not_found"}, 404)
    except KeyError:
        return response({"error": "invalid_request"}, 400)
    except PermissionError as exc:
        code = str(exc)
        return response({"error": code}, 401 if code in {"authentication_required", "invalid_auth_token"} else 403)
    except LookupError as exc:
        return response({"error": str(exc)}, 404)
    except ValueError as exc:
        code = str(exc)
        status = 409 if code in {"invite_already_consumed", "invite_not_pending", "contract_closed", "invites_already_sent", "document_locked_after_invite", "contract_not_fully_signed", "contract_no_taken"} else (410 if code == "invite_expired" else 400)
        return response({"error": code}, status)
    except Exception as exc:  # noqa: BLE001
        return response({"error": "internal_error", "detail": str(exc)[:300]}, 500)
