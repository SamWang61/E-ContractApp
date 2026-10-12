"""Token and invitation state primitives／Token 與邀請狀態安全原語。"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import secrets
from typing import Any

ALLOWED_ACTIONS = {"sign", "decline", "request_changes"}
TERMINAL_STATES = {"signed", "declined", "changes_requested", "expired", "cancelled"}

@dataclass(frozen=True)
class TokenPair:
    raw: str
    digest: str

def issue_token() -> TokenPair:
    raw = secrets.token_urlsafe(48)
    return TokenPair(raw, hashlib.sha256(raw.encode()).hexdigest())

def token_digest(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()

def validate_action(invite: dict[str, Any], action: str, now: datetime | None = None) -> str | None:
    if action not in ALLOWED_ACTIONS:
        return "invalid_action"
    if invite.get("status") in TERMINAL_STATES:
        return "invite_already_consumed"
    if invite.get("status") != "pending":
        return "invite_not_pending"
    expires_at = invite.get("expiresAt")
    if not isinstance(expires_at, datetime):
        return "invalid_expiration"
    now = now or datetime.now(timezone.utc)
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at <= now:
        return "invite_expired"
    return None

def next_contract_status(action: str, remaining_pending: int) -> str:
    if action == "decline":
        return "declined"
    if action == "request_changes":
        return "changes_requested"
    return "fully_signed" if remaining_pending <= 1 else "partially_signed"
