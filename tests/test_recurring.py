"""
Unit tests for the recurring payment detection algorithm.

These tests validate the DETERMINISTIC, NON-AI recurring detector
(backend/analytics/recurring.py).  The algorithm must be:
  • Reproducible — same input always gives same output.
  • Fast — no network calls, no model loading.
  • Correct — passes all three scenarios below.

Test Scenarios:
  1. Clear monthly subscription (Netflix-like: same amount, ~30-day intervals)
     → SHOULD be detected as recurring.
  2. Irregular one-off payments (Swiggy food orders: varied amounts)
     → SHOULD NOT be flagged as recurring.
  3. Edge case: only 2 occurrences separated by ~30 days
     → SHOULD still be detected (minimum threshold is 2).
"""

import sys
from datetime import date
from pathlib import Path

import pytest

# Ensure project root is on sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.analytics.recurring import detect_recurring_payments
from backend.models.schema import Transaction, TransactionType, RecurrenceFrequency


def _make_txn(
    txn_date: date,
    merchant: str,
    amount: float,
    txn_type: TransactionType = TransactionType.DEBIT,
) -> Transaction:
    """Helper to create a Transaction for testing."""
    return Transaction(
        date=txn_date,
        raw_description=f"UPI-{merchant.upper()}-test@ybl",
        amount=amount,
        type=txn_type,
        merchant_raw=f"UPI-{merchant.upper()}-test@ybl",
        merchant_clean=merchant,
    )


class TestRecurringDetection:
    """Test suite for the recurring payment detection algorithm."""

    def test_clear_monthly_subscription(self):
        """
        Test Case 1: Clear monthly subscription.

        Netflix charges ₹199 every month on approximately the same date.
        The algorithm should detect this as a monthly recurring subscription.
        """
        transactions = [
            _make_txn(date(2025, 4, 4), "Netflix", 199.00),
            _make_txn(date(2025, 5, 3), "Netflix", 199.00),
            _make_txn(date(2025, 6, 4), "Netflix", 199.00),
            _make_txn(date(2025, 7, 3), "Netflix", 199.00),
            # Add some unrelated transactions as noise
            _make_txn(date(2025, 5, 10), "Swiggy", 350.00),
            _make_txn(date(2025, 6, 15), "Amazon", 2500.00),
        ]

        result = detect_recurring_payments(transactions)

        # Should find exactly 1 recurring subscription (Netflix)
        assert len(result) >= 1, f"Expected at least 1 recurring, got {len(result)}"

        netflix = next((r for r in result if r.merchant.lower() == "netflix"), None)
        assert netflix is not None, "Netflix should be detected as recurring"
        assert netflix.frequency == RecurrenceFrequency.MONTHLY
        assert netflix.average_amount == 199.00
        assert netflix.occurrences == 4
        assert netflix.annualized_cost == pytest.approx(199.00 * 12, rel=0.01)

    def test_irregular_one_off_payments_not_flagged(self):
        """
        Test Case 2: Irregular one-off payments should NOT be recurring.

        Swiggy food orders at irregular intervals with varying amounts.
        The algorithm should NOT flag these as recurring.
        """
        transactions = [
            _make_txn(date(2025, 6, 1), "Swiggy", 349.00),
            _make_txn(date(2025, 6, 9), "Swiggy", 520.00),
            _make_txn(date(2025, 6, 16), "Swiggy", 189.00),
            _make_txn(date(2025, 6, 23), "Swiggy", 610.00),
            _make_txn(date(2025, 6, 30), "Swiggy", 445.00),
        ]

        result = detect_recurring_payments(transactions)

        # Swiggy should NOT be flagged — amounts vary too much (>5%)
        swiggy = next((r for r in result if r.merchant.lower() == "swiggy"), None)
        assert swiggy is None, (
            "Swiggy (irregular amounts) should NOT be detected as recurring"
        )

    def test_edge_case_two_occurrences(self):
        """
        Test Case 3: Edge case — only 2 occurrences ~30 days apart.

        A gym membership with only 2 charges should still be detected
        since our minimum threshold is 2.
        """
        transactions = [
            _make_txn(date(2025, 6, 13), "Cult Fit", 999.00),
            _make_txn(date(2025, 7, 12), "Cult Fit", 999.00),
        ]

        result = detect_recurring_payments(transactions)

        assert len(result) == 1, f"Expected 1 recurring, got {len(result)}"
        gym = result[0]
        assert gym.merchant.lower() == "cult fit"
        assert gym.frequency == RecurrenceFrequency.MONTHLY
        assert gym.average_amount == 999.00
        assert gym.occurrences == 2
        assert gym.annualized_cost == pytest.approx(999.00 * 12, rel=0.01)

    def test_weekly_subscription(self):
        """
        Bonus test: Weekly subscription detection.

        A cleaning service charging ₹500 every week.
        """
        transactions = [
            _make_txn(date(2025, 6, 1), "CleanPro", 500.00),
            _make_txn(date(2025, 6, 8), "CleanPro", 500.00),
            _make_txn(date(2025, 6, 15), "CleanPro", 500.00),
            _make_txn(date(2025, 6, 22), "CleanPro", 500.00),
        ]

        result = detect_recurring_payments(transactions)

        assert len(result) == 1
        assert result[0].frequency == RecurrenceFrequency.WEEKLY
        assert result[0].annualized_cost == pytest.approx(500.00 * 52, rel=0.01)

    def test_credit_transactions_excluded(self):
        """
        Credits (salary, refunds) should NOT be flagged as subscriptions.
        """
        transactions = [
            _make_txn(date(2025, 6, 1), "Acme Corp", 85000.00, TransactionType.CREDIT),
            _make_txn(date(2025, 7, 1), "Acme Corp", 85000.00, TransactionType.CREDIT),
        ]

        result = detect_recurring_payments(transactions)
        assert len(result) == 0, "Credit transactions should not be flagged as subscriptions"

    def test_mixed_transactions_only_flags_recurring(self):
        """
        Integration test: mix of recurring and one-off transactions.
        Only genuinely recurring merchants should be detected.
        """
        transactions = [
            # Recurring: Spotify ₹119/month
            _make_txn(date(2025, 6, 7), "Spotify", 119.00),
            _make_txn(date(2025, 7, 7), "Spotify", 119.00),
            # One-off: random purchases
            _make_txn(date(2025, 6, 10), "Amazon", 3200.00),
            _make_txn(date(2025, 7, 17), "Amazon", 1850.00),
            # One-off: single Uber ride
            _make_txn(date(2025, 6, 18), "Uber", 342.00),
            # Salary (credit — should be excluded)
            _make_txn(date(2025, 6, 2), "Acme Corp", 85000.00, TransactionType.CREDIT),
            _make_txn(date(2025, 7, 1), "Acme Corp", 85000.00, TransactionType.CREDIT),
        ]

        result = detect_recurring_payments(transactions)

        merchants = [r.merchant.lower() for r in result]
        assert "spotify" in merchants, "Spotify should be detected"
        assert "amazon" not in merchants, "Amazon (varying amounts) should not be detected"
        assert "uber" not in merchants, "Uber (single occurrence) should not be detected"
        assert "acme corp" not in merchants, "Credits should not be detected"
