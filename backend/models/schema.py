"""
Pydantic data models for the Smart Expense Intelligence System.

These models serve as the single source of truth for data shape across the
entire pipeline — ingestion, categorization, analytics, storage, and API.
Using Pydantic v2 ensures runtime validation at every boundary.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


# ─── Enums ────────────────────────────────────────────────────────────────────


class TransactionType(str, Enum):
    """Whether money left the account (debit) or entered it (credit)."""
    DEBIT = "debit"
    CREDIT = "credit"


class Category(str, Enum):
    """
    Spending categories.

    WHY AI IS USED FOR CATEGORIZATION (interview talking-point):
    ─────────────────────────────────────────────────────────────
    Transaction descriptions are wildly inconsistent across banks,
    merchants, and payment gateways.  A rule-based system would need
    hundreds of hand-maintained regex patterns and would still fail on
    unseen merchants.  An LLM can generalize from the merchant name and
    context, achieving >90 % accuracy on first pass.  We still cache the
    result per merchant so each unique merchant triggers at most ONE API
    call — making costs predictable and low.
    """
    FOOD = "food"
    RENT = "rent"
    TRAVEL = "travel"
    SHOPPING = "shopping"
    UTILITIES = "utilities"
    ENTERTAINMENT = "entertainment"
    SUBSCRIPTIONS = "subscriptions"
    HEALTHCARE = "healthcare"
    TRANSFERS = "transfers"
    SALARY = "salary"
    OTHER = "other"
    UNCATEGORIZED = "uncategorized"


class RecurrenceFrequency(str, Enum):
    """Detected payment frequency for recurring subscriptions."""
    WEEKLY = "weekly"
    BI_WEEKLY = "bi-weekly"
    MONTHLY = "monthly"
    ANNUAL = "annual"


# ─── Core Transaction Model ──────────────────────────────────────────────────


class Transaction(BaseModel):
    """A single parsed bank-statement row."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str = "default_user"
    date: date
    raw_description: str
    amount: float
    type: TransactionType
    merchant_raw: str = ""          # raw merchant substring from description
    merchant_clean: str = ""        # cleaned name (regex / LLM)
    category: Category = Category.UNCATEGORIZED
    confidence: float = 0.0         # 0-1  categorization confidence
    is_user_override: bool = False  # True if user manually corrected category



# ─── Categorization ──────────────────────────────────────────────────────────


class CategorizationResult(BaseModel):
    """Result from the AI categorizer for a single transaction."""
    transaction_id: str
    category: Category
    clean_merchant_name: str
    confidence: float = Field(ge=0.0, le=1.0)


class CategorizationBatchRequest(BaseModel):
    """A lightweight transaction summary sent to the LLM for categorization."""
    transaction_id: str
    merchant_name: str
    amount: float
    type: str  # "debit" or "credit"


# ─── Recurring Subscriptions ─────────────────────────────────────────────────


class RecurringSubscription(BaseModel):
    """
    A group of transactions flagged as a recurring payment.

    WHY THIS IS DETERMINISTIC / NO AI (interview talking-point):
    ─────────────────────────────────────────────────────────────
    Recurring-payment detection is a well-defined, constrained problem:
    "Are there ≥2 charges of similar amount at regular intervals to the
    same merchant?"  This can be solved with simple grouping, variance
    checks, and interval arithmetic.  Using AI here would be slower, more
    expensive, non-deterministic, and harder to unit-test.  A pure
    algorithm is faster, free, reproducible, and trivially testable.
    """
    merchant: str
    frequency: RecurrenceFrequency
    average_amount: float
    occurrences: int
    annualized_cost: float
    first_seen: date
    last_seen: date
    transaction_ids: list[str] = []


# ─── Cash-Flow Forecast ──────────────────────────────────────────────────────


class CashFlowForecast(BaseModel):
    """
    Result of the forward-looking cash-flow projection.

    WHY SIMPLE STATISTICS INSTEAD OF ML (interview talking-point):
    ───────────────────────────────────────────────────────────────
    A 30-day rolling-average spend rate projected linearly is:
      • Explainable — you can show the formula in one line.
      • Auditable  — a user can verify the math by hand.
      • Stable     — no model drift, no retraining, no surprise outputs.
    ML models (ARIMA, Prophet, etc.) would add complexity, dependencies,
    and "black-box" risk for marginal accuracy improvement on a personal
    finance projection that spans only 1–4 weeks.
    """
    current_balance: float
    daily_spend_rate: float            # average ₹/day over the lookback window
    projected_end_of_month_balance: float
    will_run_short: bool
    projected_shortfall_date: Optional[date] = None
    projected_shortfall_amount: Optional[float] = None
    upcoming_recurring_total: float    # sum of recurring charges still due this month
    days_remaining: int


# ─── API Request / Response helpers ──────────────────────────────────────────


class CategoryOverride(BaseModel):
    """User manually corrects the AI-assigned category for a transaction."""
    transaction_id: str
    new_category: Category


class ChatQueryRequest(BaseModel):
    query: str


class ChatQueryResponse(BaseModel):
    query: str
    answer: str
    timestamp: str


class UploadResponse(BaseModel):
    """Response after ingesting a statement file."""
    transactions_parsed: int
    message: str


class RiskSeverity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class RiskCheck(BaseModel):
    check_name: str
    passed: bool
    severity: RiskSeverity
    description: str
    details: Optional[str] = None


class CounterpartyStat(BaseModel):
    name: str
    total_amount: float
    transaction_count: int
    type: str  # "inflow" or "outflow"


class FinancialHealthScore(BaseModel):
    overall_score: int  # 0 - 1000
    grade: str  # Excellent, Good, Fair, Needs Attention
    risk_level: str  # Low Risk, Moderate Risk, High Risk
    volatility_score: float  # 0.00 (stable) to 1.00 (erratic)
    average_daily_balance: float
    monthly_inflow_avg: float
    monthly_outflow_avg: float
    savings_rate: float  # percentage e.g. 24.5%
    debt_burden_ratio: float  # percentage e.g. 15.0%
    score_breakdown: dict[str, int]  # category score components


class ExecutiveIntelligenceReport(BaseModel):
    health_score: FinancialHealthScore
    risk_checks: list[RiskCheck]
    top_counterparties: list[CounterpartyStat]
    payment_mode_breakdown: dict[str, float]  # UPI, NEFT, Card, Cash, etc.
    monthly_trends: list[dict]
    underwriting_verdict: str


class AnalysisSummary(BaseModel):
    """High-level numbers for the dashboard KPI strip."""
    total_transactions: int
    total_debits: float
    total_credits: float
    net_balance: float
    categories_breakdown: dict[str, float]  # category → total amount
    recurring_count: int
    forecast: Optional[CashFlowForecast] = None
    health_score: Optional[FinancialHealthScore] = None



# ─── Auth Models ─────────────────────────────────────────────────────────────


class SendOtpRequest(BaseModel):
    email: str
    intent: Optional[str] = None  # "signup", "signin", or None



class SendOtpResponse(BaseModel):
    success: bool
    message: str
    email: str
    is_new_user: bool


class VerifyOtpRequest(BaseModel):
    email: str
    otp: str


class UserInfo(BaseModel):
    id: str
    email: str
    created_at: str
    last_login: Optional[str] = None


class UserProfileUpdateRequest(BaseModel):
    full_name: Optional[str] = None
    phone: Optional[str] = None
    occupation: Optional[str] = None
    monthly_budget: Optional[float] = None
    currency: Optional[str] = "INR"
    city: Optional[str] = None
    bio: Optional[str] = None


class UserProfileResponse(BaseModel):
    id: str
    email: str
    full_name: Optional[str] = None
    phone: Optional[str] = None
    occupation: Optional[str] = None
    monthly_budget: Optional[float] = 0.0
    currency: Optional[str] = "INR"
    city: Optional[str] = None
    bio: Optional[str] = None
    created_at: str
    last_login: Optional[str] = None
    total_statements: Optional[int] = 0
    total_transactions: Optional[int] = 0


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserInfo
    message: str
    is_new_user: bool = False


