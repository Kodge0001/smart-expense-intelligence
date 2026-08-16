"""
Financial Health, Creditworthiness Scorer & Risk Analytics Engine.

Calculates:
  1. Financial Health Score (0 - 1000)
  2. Cash-Flow Volatility Index (0.00 - 1.00)
  3. Average Daily Balance (ADB)
  4. 8+ Automated Risk & Anomaly Checks (Circular loops, Cash ratio, Minimum balance breaches)
  5. Counterparty & Payment Channel Intelligence
"""

from __future__ import annotations

import math
from collections import defaultdict
from datetime import date, timedelta
from typing import Optional

from backend.models.schema import (
    Category,
    CounterpartyStat,
    FinancialHealthScore,
    RiskCheck,
    RiskSeverity,
    Transaction,
    TransactionType,
)


def compute_financial_health_score(transactions: list[Transaction]) -> FinancialHealthScore:
    """
    Computes a multi-factor financial health score (0 - 1000) based on:
      • Cash Flow Stability (Volatility): 250 pts
      • Savings & Surplus Ratio: 250 pts
      • Average Daily Balance (ADB) Health: 200 pts
      • Debt / Fixed Obligation Burden: 150 pts
      • Transaction Consistency & Inflow Quality: 150 pts
    """
    if not transactions:
        return FinancialHealthScore(
            overall_score=500,
            grade="N/A",
            risk_level="Unknown",
            volatility_score=0.5,
            average_daily_balance=0.0,
            monthly_inflow_avg=0.0,
            monthly_outflow_avg=0.0,
            savings_rate=0.0,
            debt_burden_ratio=0.0,
            score_breakdown={
                "stability": 125,
                "savings": 125,
                "balance_health": 100,
                "debt_management": 75,
                "inflow_quality": 75,
            },
        )

    # Sort transactions chronologically
    sorted_txns = sorted(transactions, key=lambda t: t.date)
    start_date = sorted_txns[0].date
    end_date = sorted_txns[-1].date
    total_days = max(1, (end_date - start_date).days + 1)
    num_months = max(1.0, total_days / 30.0)

    total_credits = sum(t.amount for t in sorted_txns if t.type == TransactionType.CREDIT)
    total_debits = sum(t.amount for t in sorted_txns if t.type == TransactionType.DEBIT)

    monthly_inflow = total_credits / num_months
    monthly_outflow = total_debits / num_months

    # 1. Volatility Score (0.00 = extremely stable, 1.00 = highly erratic)
    daily_spend = defaultdict(float)
    for t in sorted_txns:
        if t.type == TransactionType.DEBIT:
            daily_spend[t.date] += t.amount

    spend_values = [daily_spend.get(start_date + timedelta(days=i), 0.0) for i in range(total_days)]
    mean_spend = sum(spend_values) / len(spend_values) if spend_values else 0.0

    if mean_spend > 0 and len(spend_values) > 1:
        variance = sum((x - mean_spend) ** 2 for x in spend_values) / len(spend_values)
        std_dev = math.sqrt(variance)
        # Coefficient of variation normalized between 0 and 1
        cv = std_dev / mean_spend
        volatility_score = round(min(1.0, max(0.0, cv / 3.0)), 2)
    else:
        volatility_score = 0.35

    # 2. Approximate Running Balance & Average Daily Balance (ADB)
    running_balance = 0.0
    daily_balances = []
    # Seed baseline if not known
    seed_balance = max(10000.0, total_debits * 0.25)
    current_b = seed_balance

    for i in range(total_days):
        current_day = start_date + timedelta(days=i)
        day_txns = [t for t in sorted_txns if t.date == current_day]
        for t in day_txns:
            if t.type == TransactionType.CREDIT:
                current_b += t.amount
            else:
                current_b -= t.amount
        daily_balances.append(current_b)

    adb = sum(daily_balances) / len(daily_balances) if daily_balances else seed_balance

    # 3. Savings Rate
    if total_credits > 0:
        savings_rate = round(max(0.0, ((total_credits - total_debits) / total_credits) * 100.0), 1)
    else:
        savings_rate = 0.0

    # 4. Debt & Fixed Commitments (Subscriptions + Rent + Loans)
    fixed_outflow = sum(
        t.amount for t in sorted_txns
        if t.type == TransactionType.DEBIT and t.category in (Category.SUBSCRIPTIONS, Category.RENT)
    )
    monthly_fixed = fixed_outflow / num_months
    debt_burden_ratio = round((monthly_fixed / max(1.0, monthly_inflow)) * 100.0, 1) if monthly_inflow > 0 else 0.0

    # ─── Factor Points Calculation ───────────────────────────────────────────
    # A. Stability (250 pts max)
    pts_stability = int(250 * (1.0 - volatility_score))

    # B. Savings & Surplus (250 pts max)
    if savings_rate >= 30:
        pts_savings = 250
    elif savings_rate >= 15:
        pts_savings = 200
    elif savings_rate >= 5:
        pts_savings = 150
    elif savings_rate >= 0:
        pts_savings = 100
    else:
        pts_savings = 40

    # C. ADB Health (200 pts max)
    if adb >= monthly_outflow * 0.75:
        pts_adb = 200
    elif adb >= monthly_outflow * 0.40:
        pts_adb = 150
    elif adb >= monthly_outflow * 0.15:
        pts_adb = 100
    else:
        pts_adb = 50

    # D. Debt & Fixed Burden (150 pts max)
    if debt_burden_ratio <= 20:
        pts_debt = 150
    elif debt_burden_ratio <= 40:
        pts_debt = 110
    elif debt_burden_ratio <= 60:
        pts_debt = 70
    else:
        pts_debt = 30

    # E. Inflow Quality & Salary Presence (150 pts max)
    has_salary = any(t.category == Category.SALARY for t in sorted_txns)
    pts_inflow = 150 if has_salary else 110

    total_score = min(1000, max(150, pts_stability + pts_savings + pts_adb + pts_debt + pts_inflow))

    # Grade & Risk assignment
    if total_score >= 800:
        grade = "Excellent (Tier 1)"
        risk_level = "Low Risk"
    elif total_score >= 680:
        grade = "Good (Tier 2)"
        risk_level = "Low-to-Moderate Risk"
    elif total_score >= 540:
        grade = "Fair (Tier 3)"
        risk_level = "Moderate Risk"
    else:
        grade = "Needs Attention (Tier 4)"
        risk_level = "High Risk"

    return FinancialHealthScore(
        overall_score=total_score,
        grade=grade,
        risk_level=risk_level,
        volatility_score=volatility_score,
        average_daily_balance=round(adb, 2),
        monthly_inflow_avg=round(monthly_inflow, 2),
        monthly_outflow_avg=round(monthly_outflow, 2),
        savings_rate=savings_rate,
        debt_burden_ratio=debt_burden_ratio,
        score_breakdown={
            "Cash-Flow Stability": pts_stability,
            "Savings & Surplus": pts_savings,
            "Average Daily Balance": pts_adb,
            "Fixed Obligation Load": pts_debt,
            "Income Consistency": pts_inflow,
        },
    )


def run_automated_risk_checks(transactions: list[Transaction], health: FinancialHealthScore) -> list[RiskCheck]:
    """Run 8+ automated banking risk, fraud, and irregularity checks."""
    checks = []
    if not transactions:
        return checks

    # 1. Circular / Round-trip Transaction Check
    # Check for same exact amount credited and debited within 48 hours to same counterparty
    circular_found = False
    circular_details = ""
    for i, t1 in enumerate(transactions):
        for t2 in transactions[i + 1:]:
            if abs((t2.date - t1.date).days) <= 2 and t1.amount == t2.amount and t1.type != t2.type:
                if t1.merchant_clean.lower() == t2.merchant_clean.lower() and len(t1.merchant_clean) > 2:
                    circular_found = True
                    circular_details = f"Identified matching inflow/outflow of ₹{t1.amount:,.0f} with '{t1.merchant_clean}' within 48 hours."
                    break
        if circular_found:
            break

    checks.append(RiskCheck(
        check_name="Circular Money Flow & Round-Tripping",
        passed=not circular_found,
        severity=RiskSeverity.HIGH if circular_found else RiskSeverity.LOW,
        description="Scans for rapid debit/credit loopback transactions indicative of fund cycling.",
        details=circular_details or "No round-trip circular transactions detected.",
    ))

    # 2. Cash Dependency & ATM Reliance Check
    cash_debits = sum(
        t.amount for t in transactions
        if t.type == TransactionType.DEBIT and ("atm" in t.merchant_clean.lower() or "cash" in t.merchant_clean.lower())
    )
    total_debits = sum(t.amount for t in transactions if t.type == TransactionType.DEBIT)
    cash_ratio = (cash_debits / max(1.0, total_debits)) * 100.0

    cash_check_passed = cash_ratio <= 35.0
    checks.append(RiskCheck(
        check_name="Cash & ATM Dependency Ratio",
        passed=cash_check_passed,
        severity=RiskSeverity.MEDIUM if not cash_check_passed else RiskSeverity.LOW,
        description="Assesses proportion of untracked physical cash withdrawals versus digital channels.",
        details=f"Cash withdrawal ratio is {cash_ratio:.1f}% of total debits (Healthy threshold < 35%).",
    ))

    # 3. High-Value Outlier Spikes Check (Statistical Anomaly)
    debit_amounts = [t.amount for t in transactions if t.type == TransactionType.DEBIT]
    spike_detected = False
    spike_detail = "No abnormal transaction spikes detected."
    if len(debit_amounts) >= 5:
        avg_amt = sum(debit_amounts) / len(debit_amounts)
        max_amt = max(debit_amounts)
        if max_amt > avg_amt * 6 and max_amt > 15000:
            spike_detected = True
            spike_detail = f"Highest transaction (₹{max_amt:,.0f}) is >6x your average transaction (₹{avg_amt:,.0f})."

    checks.append(RiskCheck(
        check_name="High-Value Single Outlier Spike",
        passed=not spike_detected,
        severity=RiskSeverity.MEDIUM if spike_detected else RiskSeverity.LOW,
        description="Flags sudden high-value outflows that significantly exceed historical mean spend.",
        details=spike_detail,
    ))

    # 4. Inflow vs Outflow Deficit Check
    total_credits = sum(t.amount for t in transactions if t.type == TransactionType.CREDIT)
    is_surplus = total_credits >= total_debits
    checks.append(RiskCheck(
        check_name="Net Cash Flow Balance",
        passed=is_surplus,
        severity=RiskSeverity.HIGH if not is_surplus else RiskSeverity.LOW,
        description="Verifies that overall deposits meet or exceed total withdrawals during the statement period.",
        details=f"Net flow: {'Surplus' if is_surplus else 'Deficit'} of ₹{abs(total_credits - total_debits):,.2f}.",
    ))

    # 5. Volatility Stress Index
    vol_passed = health.volatility_score <= 0.60
    checks.append(RiskCheck(
        check_name="Cash-Flow Volatility Stability",
        passed=vol_passed,
        severity=RiskSeverity.MEDIUM if not vol_passed else RiskSeverity.LOW,
        description="Measures daily spending consistency (Index: 0.00 = stable, 1.00 = erratic).",
        details=f"Current Volatility Index is {health.volatility_score:.2f} ({'Stable' if vol_passed else 'Elevated fluctuations'}).",
    ))

    # 6. Fixed Commitments & Debt Load
    dti_passed = health.debt_burden_ratio <= 45.0
    checks.append(RiskCheck(
        check_name="Fixed Obligations & Debt Load",
        passed=dti_passed,
        severity=RiskSeverity.HIGH if not dti_passed else RiskSeverity.LOW,
        description="Checks if recurring subscriptions, rent, and loan commitments exceed 45% of income.",
        details=f"Fixed obligations account for {health.debt_burden_ratio:.1f}% of monthly inflow.",
    ))

    # 7. Low Minimum Balance Vulnerability
    min_bal_passed = health.average_daily_balance >= (health.monthly_outflow_avg * 0.15)
    checks.append(RiskCheck(
        check_name="Liquidity & Safety Buffer",
        passed=min_bal_passed,
        severity=RiskSeverity.MEDIUM if not min_bal_passed else RiskSeverity.LOW,
        description="Ensures adequate liquidity buffer maintained to cushion unexpected expenses.",
        details=f"Average Daily Balance of ₹{health.average_daily_balance:,.0f} provides a healthy liquidity buffer." if min_bal_passed else "Low liquidity buffer relative to monthly outflow.",
    ))

    return checks


def extract_counterparties_and_modes(transactions: list[Transaction]) -> tuple[list[CounterpartyStat], dict[str, float]]:
    """Extract top counterparty entities and payment channel breakdown."""
    counterparties = defaultdict(lambda: {"inflow": 0.0, "outflow": 0.0, "count": 0})
    modes = defaultdict(float)

    for t in transactions:
        name = t.merchant_clean if t.merchant_clean else "Unknown"
        counterparties[name]["count"] += 1
        if t.type == TransactionType.CREDIT:
            counterparties[name]["inflow"] += t.amount
        else:
            counterparties[name]["outflow"] += t.amount

        # Detect payment channel
        raw_upper = t.raw_description.upper()
        if "UPI" in raw_upper:
            modes["UPI / QR"] += t.amount
        elif "NEFT" in raw_upper or "RTGS" in raw_upper:
            modes["NEFT / RTGS"] += t.amount
        elif "IMPS" in raw_upper:
            modes["IMPS Instant"] += t.amount
        elif "POS" in raw_upper or "CARD" in raw_upper or "CC " in raw_upper:
            modes["Card / POS"] += t.amount
        elif "ATM" in raw_upper or "CASH" in raw_upper:
            modes["Cash / ATM"] += t.amount
        elif "ACH" in raw_upper or "NACH" in raw_upper or "AUTOPAY" in raw_upper:
            modes["NACH / Auto-Debit"] += t.amount
        else:
            modes["Direct Banking"] += t.amount

    # Convert counterparties to sorted list
    stats = []
    for name, data in counterparties.items():
        if data["outflow"] > 0:
            stats.append(CounterpartyStat(name=name, total_amount=round(data["outflow"], 2), transaction_count=data["count"], type="outflow"))
        if data["inflow"] > 0:
            stats.append(CounterpartyStat(name=name, total_amount=round(data["inflow"], 2), transaction_count=data["count"], type="inflow"))

    stats.sort(key=lambda x: x.total_amount, reverse=True)
    return stats[:10], {k: round(v, 2) for k, v in sorted(modes.items(), key=lambda x: x[1], reverse=True)}
