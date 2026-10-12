from datetime import datetime, timedelta, timezone
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parents[1] / "full" / "functions"))

from signature_service import issue_token, token_digest, validate_action, next_contract_status


def test_token_is_random_and_hashed():
    first, second = issue_token(), issue_token()
    assert first.raw != second.raw
    assert token_digest(first.raw) == first.digest
    assert first.raw not in first.digest


def test_expired_and_consumed_invites_are_rejected():
    expired = {"status": "pending", "expiresAt": datetime.now(timezone.utc) - timedelta(seconds=1)}
    assert validate_action(expired, "sign") == "invite_expired"
    consumed = {"status": "signed", "expiresAt": datetime.now(timezone.utc) + timedelta(days=1)}
    assert validate_action(consumed, "sign") == "invite_already_consumed"


def test_state_machine():
    assert next_contract_status("sign", 1) == "fully_signed"
    assert next_contract_status("sign", 2) == "partially_signed"
    assert next_contract_status("decline", 2) == "declined"
    assert next_contract_status("request_changes", 2) == "changes_requested"
