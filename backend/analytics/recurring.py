"""
Recurring payment detector — pure deterministic algorithm, NO AI.

WHY NO AI HERE (interview talking-point):
─────────────────────────────────────────
Recurring-payment detection is a well-defined, constrained problem:
  "Are there ≥2 charges of *similar amount* at *regular intervals* to
   the *same merchant*?"

This can be solved with simple grouping, variance checks, and interval
arithmetic.  Using AI here would be:
  • Slower       — network round-trip for each analysis
  • More expensive — API costs for a deterministic question
  • Non-deterministic — different runs could give different answers
  • Harder to test — can't write reliable unit tests against AI output

A pure algorithm is faster, free, 100% reproducible, and trivially
unit-testable.  The 3 test cases in tests/test_recurring.py prove
correctness across normal, edge-case, and negative scenarios.

ALGORITHM:
  1. Group debit transactions by cleaned merchant name.
  2. For each group with ≥2 transactions:
     a. Check AMOUNT consistency: all amounts within ±5% of the mean.
     b. Sort by date and compute intervals between consecutive transactions.
     c. Check INTERVAL regularity: detect weekly, bi-weekly, monthly, or
        annual patterns using tolerance windows.
  3. If both checks pass, flag as recurring and compute annualized cost.
"""

from __future__ import annotations

from datetime import date, timedelta
from statistics import mean, stdev

from backend.models.schema import (
    RecurringSubscription,
    RecurrenceFrequency,
    Transaction,
    TransactionType,
)


# ─── Configuration ────────────────────────────────────────────────────────────

AMOUNT_TOLERANCE_PCT = 0.05    # 5% variance allowed between charges
MIN_OCCURRENCES = 2            # Need at least 2 charges to detect recurrence

# (expected_days, tolerance_days, frequency_enum, annual_multiplier)
FREQUENCY_PATTERNS: list[tuple[float, float, RecurrenceFrequency, float]] = [
    (7,   3,  RecurrenceFrequency.WEEKLY,    52),
    (14,  4,  RecurrenceFrequency.BI_WEEKLY, 26),
    (30,  5,  RecurrenceFrequency.MONTHLY,   12),
    (365, 15, RecurrenceFrequency.ANNUAL,     1),
]


# ─── Public API ───────────────────────────────────────────────────────────────


def detect_recurring_payments(transactions: list[Transaction]) -> list[RecurringSubscription]:
    """
    Detect recurring subscription payments from a list of transactions.

    This is a deterministic algorithm with no AI/ML components.
    It groups debit transactions by merchant, checks amount consistency
    and interval regularity, and flags matching groups as recurring.

    Args:
        transactions: All parsed transactions (debits and credits).

    Returns:
        List of RecurringSubscription objects, sorted by annualized cost
        descending.
    """
    # Step 1: Filter to debits only and group by merchant
    merchant_groups = _group_by_merchant(transactions)

    recurring: list[RecurringSubscription] = []

    for merchant, txns in merchant_groups.items():
        if len(txns) < MIN_OCCURRENCES:
            continue

        # Step 2a: Check amount consistency
        if not _amounts_are_consistent(txns):
            continue

        # Step 2b: Check interval regularity
        frequency_result = _detect_frequency(txns)
        if frequency_result is None:
            continue

        frequency, annual_multiplier = frequency_result
        avg_amount = mean(t.amount for t in txns)
        annualized = avg_amount * annual_multiplier

        sorted_txns = sorted(txns, key=lambda t: t.date)
        recurring.append(RecurringSubscription(
            merchant=merchant,
            frequency=frequency,
            average_amount=round(avg_amount, 2),
            occurrences=len(txns),
            annualized_cost=round(annualized, 2),
            first_seen=sorted_txns[0].date,
            last_seen=sorted_txns[-1].date,
            transaction_ids=[t.id for t in sorted_txns],
        ))

    # Sort by annualized cost descending
    recurring.sort(key=lambda r: r.annualized_cost, reverse=True)
    return recurring


# ─── Internal helpers ─────────────────────────────────────────────────────────


def _group_by_merchant(transactions: list[Transaction]) -> dict[str, list[Transaction]]:
    """Group debit transactions by cleaned merchant name (case-insensitive)."""
    groups: dict[str, list[Transaction]] = {}
    for txn in transactions:
        if txn.type != TransactionType.DEBIT:
            continue
        key = txn.merchant_clean.lower().strip()
        if not key or key == "unknown":
            continue
        groups.setdefault(key, []).append(txn)
    return groups


def _amounts_are_consistent(txns: list[Transaction]) -> bool:
    """
    Check if all transaction amounts in a group are within ±5% of the mean.

    For example, Netflix charging ₹199.00 every month would pass.
    Random Swiggy orders of ₹180, ₹450, ₹320 would fail.
    """
    amounts = [t.amount for t in txns]
    avg = mean(amounts)
    if avg == 0:
        return False

    for amt in amounts:
        deviation = abs(amt - avg) / avg
        if deviation > AMOUNT_TOLERANCE_PCT:
            return False

    return True


def _detect_frequency(txns: list[Transaction]) -> tuple[RecurrenceFrequency, float] | None:
    """
    Determine the payment frequency by analyzing intervals between
    consecutive transactions.

    Returns (frequency_enum, annual_multiplier) or None if no pattern matches.
    """
    sorted_txns = sorted(txns, key=lambda t: t.date)

    # Compute intervals in days between consecutive transactions
    intervals: list[int] = []
    for i in range(1, len(sorted_txns)):
        delta = (sorted_txns[i].date - sorted_txns[i - 1].date).days
        intervals.append(delta)

    if not intervals:
        return None

    avg_interval = mean(intervals)

    # Match against known frequency patterns
    for expected_days, tolerance, frequency, annual_mult in FREQUENCY_PATTERNS:
        if abs(avg_interval - expected_days) <= tolerance:
            # Verify that individual intervals are also within tolerance
            if all(abs(iv - expected_days) <= tolerance * 1.5 for iv in intervals):
                return frequency, annual_mult

    return None
