"""
Cash-flow forecasting — simple statistical projection, NO AI/ML.

WHY SIMPLE STATISTICS INSTEAD OF ML (interview talking-point):
──────────────────────────────────────────────────────────────
A 30-day rolling-average spend rate projected linearly is:
  • Explainable — you can show the formula in one line of math.
  • Auditable   — a user can verify the projection by hand.
  • Stable      — no model drift, no retraining, no surprise outputs.
  • Lightweight — zero external dependencies beyond Python stdlib.

ML models like ARIMA, Prophet, or LSTM would add significant complexity,
heavy dependencies, and training/tuning overhead — all for marginal
accuracy improvement on a personal finance projection spanning 1–4 weeks.
The simplicity here is intentional and defensible.

ALGORITHM:
  1. Calculate the user's current balance (sum of all credits − debits).
  2. Compute the daily spend rate as the average daily debit over the
     last 30 days (or all available data if < 30 days).
  3. Project forward day-by-day to end of month:
     • Subtract daily spend rate each day.
     • Add known upcoming recurring credits (salary).
     • Subtract known upcoming recurring debits (subscriptions).
  4. If the projected balance drops below zero on any day, flag a
     shortfall with the exact date and amount.
"""

from __future__ import annotations

import calendar
from collections import defaultdict
from datetime import date, timedelta
from statistics import mean

from backend.models.schema import (
    CashFlowForecast,
    RecurringSubscription,
    Transaction,
    TransactionType,
)


def forecast_cash_flow(
    transactions: list[Transaction],
    recurring: list[RecurringSubscription] | None = None,
    reference_date: date | None = None,
) -> CashFlowForecast:
    """
    Project cash flow to end of month and detect potential shortfalls.

    This uses a simple linear projection based on historical daily spend
    rate — intentionally straightforward and explainable.

    Args:
        transactions: All parsed transactions.
        recurring: Detected recurring subscriptions (for upcoming charges).
        reference_date: The "today" date for projection (defaults to the
                       latest transaction date, useful for testing with
                       synthetic data).

    Returns:
        CashFlowForecast with shortfall prediction.
    """
    if not transactions:
        return CashFlowForecast(
            current_balance=0,
            daily_spend_rate=0,
            projected_end_of_month_balance=0,
            will_run_short=False,
            upcoming_recurring_total=0,
            days_remaining=0,
        )

    # Use the latest transaction date as reference if not provided
    if reference_date is None:
        reference_date = max(t.date for t in transactions)

    # ── Step 1: Calculate current balance ──
    total_credits = sum(t.amount for t in transactions if t.type == TransactionType.CREDIT)
    total_debits = sum(t.amount for t in transactions if t.type == TransactionType.DEBIT)
    current_balance = total_credits - total_debits

    # ── Step 2: Calculate daily spend rate (30-day rolling average) ──
    lookback_start = reference_date - timedelta(days=30)
    recent_debits = [
        t for t in transactions
        if t.type == TransactionType.DEBIT and t.date >= lookback_start and t.date <= reference_date
    ]

    if recent_debits:
        # Group by day and calculate daily totals
        daily_totals: dict[date, float] = defaultdict(float)
        for t in recent_debits:
            daily_totals[t.date] += t.amount

        # Average daily spend (including zero-spend days in the window)
        days_in_window = max((reference_date - lookback_start).days, 1)
        total_recent_spend = sum(daily_totals.values())
        daily_spend_rate = total_recent_spend / days_in_window
    else:
        daily_spend_rate = 0

    # ── Step 3: Calculate days remaining in projection window ──
    _, last_day = calendar.monthrange(reference_date.year, reference_date.month)
    end_of_month = date(reference_date.year, reference_date.month, last_day)
    days_to_eom = (end_of_month - reference_date).days

    # If near or at month-end (< 15 days left), project 30 days forward
    if days_to_eom < 15:
        days_remaining = 30
        end_of_window = reference_date + timedelta(days=30)
    else:
        days_remaining = days_to_eom
        end_of_window = end_of_month

    # ── Step 4: Calculate upcoming recurring charges ──
    upcoming_recurring_total = 0.0
    if recurring:
        for sub in recurring:
            # Estimate if this subscription will charge again within the projection window
            if sub.frequency.value == "monthly":
                expected_next = sub.last_seen + timedelta(days=30)
            elif sub.frequency.value == "weekly":
                expected_next = sub.last_seen + timedelta(days=7)
            elif sub.frequency.value == "bi-weekly":
                expected_next = sub.last_seen + timedelta(days=14)
            else:
                continue

            if reference_date < expected_next <= end_of_window:
                upcoming_recurring_total += sub.average_amount

    # ── Step 5: Project forward day by day ──
    projected_balance = current_balance
    projected_spend = daily_spend_rate * days_remaining + upcoming_recurring_total
    projected_end_balance = current_balance - projected_spend

    # Check for shortfall day-by-day
    shortfall_date = None
    shortfall_amount = None
    running_balance = current_balance

    for day_offset in range(1, days_remaining + 1):
        check_date = reference_date + timedelta(days=day_offset)
        running_balance -= daily_spend_rate

        # Check if any recurring payment falls on this day
        if recurring:
            for sub in recurring:
                if sub.frequency.value == "monthly":
                    expected_next = sub.last_seen + timedelta(days=30)
                elif sub.frequency.value == "weekly":
                    expected_next = sub.last_seen + timedelta(days=7)
                elif sub.frequency.value == "bi-weekly":
                    expected_next = sub.last_seen + timedelta(days=14)
                else:
                    continue

                if expected_next == check_date:
                    running_balance -= sub.average_amount

        if running_balance < 0 and shortfall_date is None:
            shortfall_date = check_date
            shortfall_amount = abs(running_balance)

    will_run_short = shortfall_date is not None

    return CashFlowForecast(
        current_balance=round(current_balance, 2),
        daily_spend_rate=round(daily_spend_rate, 2),
        projected_end_of_month_balance=round(projected_end_balance, 2),
        will_run_short=will_run_short,
        projected_shortfall_date=shortfall_date,
        projected_shortfall_amount=round(shortfall_amount, 2) if shortfall_amount else None,
        upcoming_recurring_total=round(upcoming_recurring_total, 2),
        days_remaining=days_remaining,
    )
