from __future__ import annotations

from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
import base64, hashlib, os, smtplib
from typing import Any

from cryptography.fernet import Fernet
from firebase_admin import auth, firestore, initialize_app
from firebase_functions import https_fn, options

from signature_service import issue_token, token_digest, validate_action, next_contract_status

initialize_app()
DB = firestore.client()
INVITES = "signatureInvites"
KEY = base64.urlsafe_b64encode(hashlib.sha256(os.getenv("SIGNING_TOKEN_ENCRYPTION_KEY", "development-only-change-me").encode()).digest())
CIPHER = Fernet(KEY)


def response(data: dict[str, Any], status: int = 200):
    return https_fn.Response(data, status=status, mimetype="application/json")


def require_user(req):
    header = req.headers.get("Authorization", "")
    if not header.startswith("Bearer "):
        raise ValueError("authentication_required")
    try:
        return auth.verify_id_token(header[7:].strip())
    except Exception as exc:
        raise ValueError("invalid_auth_token") from exc


def contract_ref(tenant_id: str, contract_id: str):
    return DB.collection("tenants").document(tenant_id).collection("contracts").document(contract_id)


def invite_ref(tenant_id: str, contract_id: str, signer_id: str):
    return contract_ref(tenant_id, contract_id).collection(INVITES).document(signer_id)


def send_email(to: str, subject: str, text: str) -> str:
    host = os.getenv("SMTP_HOST")
    if not host:
        return "preview"
    message = EmailMessage()
    message["From"] = os.getenv("SMTP_FROM", "no-reply@example.com")
    message["To"] = to
    message["Subject"] = subject
    message.set_content(text)
    with smtplib.SMTP(host, int(os.getenv("SMTP_PORT", "587")), timeout=15) as server:
        server.starttls()
        if os.getenv("SMTP_USERNAME"):
            server.login(os.getenv("SMTP_USERNAME"), os.getenv("SMTP_PASSWORD", ""))
        server.send_message(message)
    return "sent"


def expiry(value: Any) -> datetime:
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00")) if value else datetime.now(timezone.utc) + timedelta(days=7)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    now = datetime.now(timezone.utc)
    if parsed <= now or parsed > now + timedelta(days=90):
        raise ValueError("expiration_must_be_between_now_and_90_days")
    return parsed


def locate(raw: str):
    digest = token_digest(raw)
    return next(DB.collection_group(INVITES).where("tokenHash", "==", digest).limit(1).stream()), None


def create_invite(tenant_id: str, contract_id: str, signer: dict, expires_at: datetime, title: str):
    email = str(signer.get("email", "")).strip().lower()
    signer_id = str(signer.get("id") or email)
    if "@" not in email or not signer_id:
        raise ValueError("invalid_signer")
    token = issue_token()
    ref = invite_ref(tenant_id, contract_id, signer_id)
    ref.set({"signerId": signer_id, "email": email, "role": signer.get("role", "signer"), "tokenHash": token.digest, "tokenCiphertext": CIPHER.encrypt(token.raw.encode()).decode(), "status": "pending", "expiresAt": expires_at, "createdAt": firestore.SERVER_TIMESTAMP, "updatedAt": firestore.SERVER_TIMESTAMP, "reminderCount": 0})
    url = f"{os.getenv('APP_BASE_URL', 'http://localhost:5000').rstrip('/')}/sign/{token.raw}"
    delivery = send_email(email, f"簽署邀請／Signing invitation: {title}", f"請使用專屬連結完成簽署／Use your private signing link:\n{url}\n\n期限／Expires: {expires_at.isoformat()}")
    ref.update({"emailStatus": delivery, "lastSentAt": firestore.SERVER_TIMESTAMP})
    result = {"signerId": signer_id, "email": email, "role": signer.get("role", "signer"), "emailStatus": delivery, "expiresAt": expires_at.isoformat()}
    if delivery == "preview" and os.getenv("APP_ENV") != "production":
        result["previewUrl"] = url
    return result


@https_fn.on_request(region="asia-east1", cors=options.CorsOptions(cors_origins="*", cors_methods=["get", "post", "options"]))
def api(req: https_fn.Request):
    path = req.path.rstrip("/")
    if req.method == "OPTIONS":
        return response({"ok": True})
    if req.method == "GET" and path.endswith("/health"):
        return response({"ok": True, "service": "e-contract-app-api"})
    try:
        payload = req.get_json(silent=True) or {}
        if req.method == "POST" and path.endswith("/signature/invite"):
            user = require_user(req)
            tenant_id, contract_id = str(payload["tenantId"]), str(payload["contractId"])
            contract = contract_ref(tenant_id, contract_id).get()
            if not contract.exists or contract.to_dict().get("createdBy") != user["uid"]:
                return response({"error": "owner_required"}, 403)
            expires_at = expiry(payload.get("expiresAt"))
            signers = payload.get("signers") or []
            if not signers or len(signers) > 20:
                return response({"error": "signers_required"}, 400)
            result = [create_invite(tenant_id, contract_id, signer, expires_at, contract.to_dict().get("title", "合約")) for signer in signers]
            contract_ref(tenant_id, contract_id).set({"status": "invited", "pendingSigners": len(result), "updatedAt": firestore.SERVER_TIMESTAMP}, merge=True)
            return response({"ok": True, "invites": result})
        if req.method == "GET" and path.endswith("/signature/invite"):
            raw = req.args.get("token", "")
            snap = next(DB.collection_group(INVITES).where("tokenHash", "==", token_digest(raw)).limit(1).stream(), None)
            if not snap:
                return response({"error": "invite_not_found"}, 404)
            invite = snap.to_dict() or {}
            error = validate_action(invite, "sign")
            if error:
                return response({"error": error}, 410 if error == "invite_expired" else 409)
            contract = snap.reference.parent.parent.get().to_dict() or {}
            return response({"ok": True, "invite": {"role": invite.get("role"), "email": invite.get("email"), "expiresAt": invite["expiresAt"].isoformat()}, "contract": {"id": snap.reference.parent.parent.id, "title": contract.get("title"), "summary": contract.get("summary")}})
        if req.method == "POST" and path.endswith("/signature/action"):
            action, raw = str(payload.get("action", "")), str(payload.get("token", ""))
            snap = next(DB.collection_group(INVITES).where("tokenHash", "==", token_digest(raw)).limit(1).stream(), None)
            if not snap:
                return response({"error": "invite_not_found"}, 404)
            name, reason = str(payload.get("name", "")).strip(), str(payload.get("reason", "")).strip()
            if action == "sign" and (not name or payload.get("consent") is not True):
                return response({"error": "name_and_consent_required"}, 400)
            if action in {"decline", "request_changes"} and not reason:
                return response({"error": "reason_required"}, 400)
            tx = DB.transaction()
            @firestore.transactional
            def consume(transaction):
                current = transaction.get(snap.reference).to_dict() or {}
                error = validate_action(current, action)
                if error:
                    raise ValueError(error)
                contract_ref_doc = snap.reference.parent.parent
                contract = transaction.get(contract_ref_doc).to_dict() or {}
                pending = int(contract.get("pendingSigners", 1))
                status = "signed" if action == "sign" else ("declined" if action == "decline" else "changes_requested")
                decision = {"action": action, "name": name, "reason": reason, "at": datetime.now(timezone.utc)}
                transaction.update(snap.reference, {"status": status, "decision": decision, "consumedAt": firestore.SERVER_TIMESTAMP, "updatedAt": firestore.SERVER_TIMESTAMP})
                update = {"status": next_contract_status(action, pending), "workflowState": "needs_owner_review" if action != "sign" else "active", "updatedAt": firestore.SERVER_TIMESTAMP}
                if action == "sign":
                    update["pendingSigners"] = max(0, pending - 1)
                    update["signatures"] = firestore.ArrayUnion([decision])
                transaction.update(contract_ref_doc, update)
                return {"inviteStatus": status, "status": update["status"]}
            return response({"ok": True, **consume(tx)})
        if req.method == "POST" and path.endswith("/signature/reminders"):
            require_user(req)
            now, sent = datetime.now(timezone.utc), 0
            for snap in DB.collection_group(INVITES).where("status", "==", "pending").stream():
                invite = snap.to_dict() or {}; expires_at = invite.get("expiresAt")
                if not isinstance(expires_at, datetime):
                    continue
                if expires_at <= now:
                    snap.reference.update({"status": "expired", "updatedAt": firestore.SERVER_TIMESTAMP})
                elif expires_at - now <= timedelta(days=2):
                    raw = CIPHER.decrypt(invite["tokenCiphertext"].encode()).decode()
                    title = (snap.reference.parent.parent.get().to_dict() or {}).get("title", "合約")
                    send_email(invite["email"], f"提醒簽署／Signing reminder: {title}", f"原專屬連結／Original private link: {os.getenv('APP_BASE_URL', 'http://localhost:5000')}/sign/{raw}")
                    snap.reference.update({"reminderCount": firestore.Increment(1), "lastReminderAt": firestore.SERVER_TIMESTAMP}); sent += 1
            return response({"ok": True, "remindersSent": sent})
        return response({"error": "not_found"}, 404)
    except KeyError:
        return response({"error": "invalid_request"}, 400)
    except ValueError as exc:
        return response({"error": str(exc)}, 400)
    except Exception as exc:
        return response({"error": "internal_error", "detail": str(exc)}, 500)
