"""
Tests for Email OTP Authentication, Rate Limiting, Multi-Tenant Scoping, and Dynamic Confidence Scoring.
"""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.ai.categorizer import _rule_based_categorize
from backend.auth.security import create_access_token, decode_access_token
from backend.main import app
from backend.models.schema import Category, Transaction, TransactionType
from backend.storage.db import (
    clear_transactions,
    init_db,
    load_transactions,
    save_otp,
    save_transactions,
    verify_otp,
)


@pytest.fixture(autouse=True)
def setup_database():
    init_db()
    from backend.storage.db import get_connection
    conn = get_connection()
    conn.execute("DELETE FROM otp_verifications")
    conn.execute("DELETE FROM users")
    conn.commit()
    conn.close()




def test_otp_generation_and_verification():
    email = "test_user_otp@example.com"
    otp = "654321"

    # Save OTP
    ok, msg = save_otp(email, otp)
    assert ok is True

    # Bad OTP attempt
    ok_bad, msg_bad = verify_otp(email, "000000")
    assert ok_bad is False
    assert "Incorrect code" in msg_bad

    # Good OTP attempt
    ok_good, msg_good = verify_otp(email, otp)
    assert ok_good is True


def test_otp_rate_limiting():
    email = "test_ratelimit@example.com"
    otp = "112233"

    # 1st request succeeds
    ok1, _ = save_otp(email, otp)
    assert ok1 is True

    # Immediate 2nd request should fail 60s cooldown
    ok2, msg2 = save_otp(email, "445566")
    assert ok2 is False
    assert "Please wait" in msg2


def test_jwt_token_creation_and_decoding():
    token = create_access_token(user_id="user_123", email="user123@example.com")
    assert isinstance(token, str)

    payload = decode_access_token(token)
    assert payload is not None
    assert payload["sub"] == "user_123"
    assert payload["email"] == "user123@example.com"


def test_multi_tenant_data_isolation():
    user_a = "user_alpha"
    user_b = "user_beta"

    clear_transactions(user_a)
    clear_transactions(user_b)

    txn_a = Transaction(
        id="txn_a_1",
        user_id=user_a,
        date=date(2026, 6, 1),
        raw_description="User A Spotify",
        amount=119.0,
        type=TransactionType.DEBIT,
        merchant_clean="spotify",
        category=Category.SUBSCRIPTIONS,
    )
    txn_b = Transaction(
        id="txn_b_1",
        user_id=user_b,
        date=date(2026, 6, 2),
        raw_description="User B Netflix",
        amount=649.0,
        type=TransactionType.DEBIT,
        merchant_clean="netflix",
        category=Category.SUBSCRIPTIONS,
    )

    save_transactions([txn_a], user_id=user_a)
    save_transactions([txn_b], user_id=user_b)

    txns_a = load_transactions(user_id=user_a)
    txns_b = load_transactions(user_id=user_b)

    assert len(txns_a) == 1
    assert txns_a[0].id == "txn_a_1"

    assert len(txns_b) == 1
    assert txns_b[0].id == "txn_b_1"


def test_dynamic_confidence_variance():
    """Verify confidence scores are not flat 70% and reflect calibrated merchant certainty."""
    res_netflix = _rule_based_categorize("netflix subscription", 199.0, "debit")
    res_swiggy = _rule_based_categorize("swiggy bangalore", 450.0, "debit")
    res_general = _rule_based_categorize("unknown xyz merchant 999", 50.0, "debit")
    res_salary = _rule_based_categorize("monthly payroll salary", 85000.0, "credit")

    # Confidences must vary
    confidences = {
        res_netflix.confidence,
        res_swiggy.confidence,
        res_general.confidence,
        res_salary.confidence,
    }
    assert len(confidences) > 1, f"Confidences should not be uniform: {confidences}"
    assert res_netflix.confidence >= 0.90
    assert res_general.confidence <= 0.60



def test_new_user_vs_returning_user_detection(monkeypatch):
    client = TestClient(app)
    monkeypatch.setattr("backend.main.send_otp_email", lambda email, otp: (True, "Code sent."))

    # 1. New user send-otp
    email_new = "brand_new_user@example.com"
    resp1 = client.post("/api/auth/send-otp", json={"email": email_new})
    assert resp1.status_code == 200
    data1 = resp1.json()
    assert data1["is_new_user"] is True

    # 2. Get OTP from DB and verify
    from backend.storage.db import get_connection
    conn = get_connection()
    row = conn.execute("SELECT otp_code FROM otp_verifications WHERE email = ?", (email_new,)).fetchone()
    otp_code = row["otp_code"]
    conn.close()

    resp_verify = client.post("/api/auth/verify-otp", json={"email": email_new, "otp": otp_code})
    assert resp_verify.status_code == 200
    assert resp_verify.json()["is_new_user"] is True

    # 3. Request OTP again for the same user (now returning user)
    conn = get_connection()
    conn.execute("DELETE FROM otp_verifications WHERE email = ?", (email_new,))
    conn.commit()
    conn.close()

    resp2 = client.post("/api/auth/send-otp", json={"email": email_new})
    assert resp2.status_code == 200
    data2 = resp2.json()
    assert data2["is_new_user"] is False


def test_intent_validation_rejections(monkeypatch):
    client = TestClient(app)
    monkeypatch.setattr("backend.main.send_otp_email", lambda email, otp: (True, "Code sent."))
    email_existing = "existing_intent_test@example.com"
    email_new = "non_existent_intent_test@example.com"

    # Create existing user
    from backend.storage.db import get_or_create_user
    get_or_create_user(email_existing)

    # 1. Attempt signup with existing user -> 409 conflict
    resp_signup_existing = client.post("/api/auth/send-otp", json={"email": email_existing, "intent": "signup"})
    assert resp_signup_existing.status_code == 409
    assert "already exists" in resp_signup_existing.json()["detail"]

    # 2. Attempt signin with non-existent user -> 404 not found
    resp_signin_new = client.post("/api/auth/send-otp", json={"email": email_new, "intent": "signin"})
    assert resp_signin_new.status_code == 404
    assert "No account found" in resp_signin_new.json()["detail"]



