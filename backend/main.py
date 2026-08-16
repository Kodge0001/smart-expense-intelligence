"""
FastAPI backend for the Smart Expense Intelligence System.

Exposes REST endpoints for:
  • File upload (CSV/PDF ingestion)
  • AI-powered transaction categorization
  • Recurring payment detection (pure algorithm)
  • Cash-flow forecasting (simple statistics)
  • Manual category overrides
  • Sample data loading
"""

from __future__ import annotations

import logging
import os
import sys
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from fastapi.responses import JSONResponse


# Ensure the project root is on sys.path for clean imports
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

load_dotenv(PROJECT_ROOT / ".env")

from backend.ai.categorizer import categorize_transactions
from backend.analytics.forecast import forecast_cash_flow
from backend.analytics.recurring import detect_recurring_payments
from backend.auth.email_service import send_otp_email
from backend.auth.security import create_access_token, get_current_user
from backend.ingestion.parser import parse_csv, parse_pdf
from backend.analytics.precisa_scorer import (
    compute_financial_health_score,
    extract_counterparties_and_modes,
    run_automated_risk_checks,
)
from backend.models.schema import (
    AnalysisSummary,
    AuthResponse,
    Category,
    CategoryOverride,
    CashFlowForecast,
    ChatQueryRequest,
    ChatQueryResponse,
    ExecutiveIntelligenceReport,
    FinancialHealthScore,
    RecurringSubscription,
    RiskSeverity,
    SendOtpRequest,
    SendOtpResponse,
    Transaction,
    TransactionType,
    UploadResponse,
    UserInfo,
    UserProfileResponse,
    UserProfileUpdateRequest,
    VerifyOtpRequest,
)

from backend.storage.db import (
    cache_lookup,
    cache_store,
    clear_transactions,
    get_or_create_user,
    get_user_by_email,
    init_db,
    load_transactions,
    save_otp,
    save_override,
    save_transactions,
    verify_otp,
)

# ─── Logging ──────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s │ %(name)s │ %(levelname)s │ %(message)s",
)
logger = logging.getLogger("expense-intelligence")

# ─── FastAPI App ──────────────────────────────────────────────────────────────

app = FastAPI(
    title="Smart Expense Intelligence System",
    description=(
        "Upload bank statements → AI categorization → "
        "Recurring payment detection → Cash-flow forecasting"
    ),
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup():
    """Initialize the database on application startup."""
    init_db()
    logger.info("Database initialized successfully.")


# ─── Auth Endpoints ───────────────────────────────────────────────────────────


@app.post("/api/auth/send-otp", response_model=SendOtpResponse)
async def send_otp(req: SendOtpRequest):
    """
    Generate a 6-digit OTP, enforce intent constraints (signup vs signin), rate-limits, and send via email.
    """
    import random
    email = req.email.strip().lower()
    if not email or "@" not in email:
        raise HTTPException(status_code=400, detail="Invalid email address.")

    existing_user = get_user_by_email(email)
    is_new_user = existing_user is None

    # Explicit intent validation
    if req.intent == "signup" and not is_new_user:
        raise HTTPException(
            status_code=409,
            detail="An account with this email already exists.",
        )
    elif req.intent == "signin" and is_new_user:
        raise HTTPException(
            status_code=404,
            detail="No account found with this email.",
        )

    otp_code = f"{random.randint(100000, 999999)}"
    ok, msg = save_otp(email, otp_code)
    if not ok:
        raise HTTPException(status_code=429, detail=msg)

    send_ok, send_msg = send_otp_email(email, otp_code)
    if not send_ok:
        raise HTTPException(status_code=500, detail=f"Could not send code, please try again. ({send_msg})")

    return SendOtpResponse(
        success=True,
        message=send_msg,
        email=email,
        is_new_user=is_new_user,
    )



@app.post("/api/auth/verify-otp", response_model=AuthResponse)
async def verify_otp_endpoint(req: VerifyOtpRequest):
    """
    Verify OTP entered by the user. If valid:
      - Automatically create account if first time
      - Issue signed JWT session token
    """
    email = req.email.strip().lower()
    otp = req.otp.strip()

    if not email or not otp:
        raise HTTPException(status_code=400, detail="Email and OTP code are required.")

    existing_user = get_user_by_email(email)
    is_new_user = existing_user is None

    ok, msg = verify_otp(email, otp)
    if not ok:
        raise HTTPException(status_code=400, detail=msg)

    user = get_or_create_user(email)
    token = create_access_token(user_id=user["id"], email=user["email"])

    return AuthResponse(
        access_token=token,
        token_type="bearer",
        user=UserInfo(
            id=user["id"],
            email=user["email"],
            created_at=user["created_at"],
            last_login=user.get("last_login"),
        ),
        message="Account created successfully." if is_new_user else "Welcome back! Login successful.",
        is_new_user=is_new_user,
    )



@app.get("/api/auth/me", response_model=UserInfo)
async def get_me(current_user: dict = Depends(get_current_user)):
    """Return currently logged-in user profile."""
    return UserInfo(
        id=current_user["id"],
        email=current_user["email"],
        created_at=current_user["created_at"],
        last_login=current_user.get("last_login"),
    )


@app.get("/api/profile", response_model=UserProfileResponse)
async def get_profile(current_user: dict = Depends(get_current_user)):
    """Return detailed user profile including personal details and stats."""
    user_id = current_user["id"]
    txns = load_transactions(user_id=user_id)
    return UserProfileResponse(
        id=user_id,
        email=current_user["email"],
        full_name=current_user.get("full_name") or "",
        phone=current_user.get("phone") or "",
        occupation=current_user.get("occupation") or "",
        monthly_budget=float(current_user.get("monthly_budget") or 0.0),
        currency=current_user.get("currency") or "INR",
        city=current_user.get("city") or "",
        bio=current_user.get("bio") or "",
        created_at=current_user["created_at"],
        last_login=current_user.get("last_login"),
        total_statements=1 if txns else 0,
        total_transactions=len(txns),
    )


@app.put("/api/profile", response_model=UserProfileResponse)
async def update_profile(
    req: UserProfileUpdateRequest,
    current_user: dict = Depends(get_current_user),
):
    """Update personal profile details for logged in user."""
    from backend.storage.db import update_user_profile
    user_id = current_user["id"]
    updated_user = update_user_profile(user_id, req.model_dump(exclude_unset=True))
    if not updated_user:
        raise HTTPException(status_code=404, detail="User not found.")

    txns = load_transactions(user_id=user_id)
    return UserProfileResponse(
        id=user_id,
        email=updated_user["email"],
        full_name=updated_user.get("full_name") or "",
        phone=updated_user.get("phone") or "",
        occupation=updated_user.get("occupation") or "",
        monthly_budget=float(updated_user.get("monthly_budget") or 0.0),
        currency=updated_user.get("currency") or "INR",
        city=updated_user.get("city") or "",
        bio=updated_user.get("bio") or "",
        created_at=updated_user["created_at"],
        last_login=updated_user.get("last_login"),
        total_statements=1 if txns else 0,
        total_transactions=len(txns),
    )


# ─── Endpoints (Scoped to Logged-In User) ──────────────────────────────────────


@app.post("/api/ingest", response_model=UploadResponse)
async def ingest_file(
    file: UploadFile = File(...),
    password: Optional[str] = Form(None),
    current_user: dict = Depends(get_current_user),
):
    """
    Upload and parse a bank statement file (CSV or PDF).
    Stores transactions strictly scoped to the logged-in user.
    Supports password-protected PDFs.
    """
    content = await file.read()
    filename = (file.filename or "unknown").lower()

    try:
        if filename.endswith(".pdf"):
            transactions = parse_pdf(content, password=password.strip() if password else None)
        elif filename.endswith(".csv"):
            transactions = parse_csv(content)
        else:
            raise HTTPException(
                status_code=400,
                detail="Unsupported file format. Please upload a CSV or PDF file.",
            )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


    if not transactions:
        raise HTTPException(
            status_code=400,
            detail="No transactions could be parsed from the uploaded file.",
        )

    # Assign user_id to all transactions
    user_id = current_user["id"]
    for t in transactions:
        t.user_id = user_id

    # Auto-categorize
    categorized = await categorize_transactions(
        transactions,
        cache_lookup=lambda key: cache_lookup(key, user_id=user_id),
        cache_store=lambda key, cat, conf: cache_store(key, cat, conf, user_id=user_id),
    )

    # Clear previous transactions for fresh statement ingest
    from backend.storage.db import clear_transactions
    clear_transactions(user_id=user_id)

    # Save scoped to user
    saved = save_transactions(categorized, user_id=user_id)
    logger.info(f"Ingested and categorized {saved} transactions for user {current_user['email']}")



    return UploadResponse(
        transactions_parsed=saved,
        message=f"Successfully parsed & categorized {saved} transactions from {filename}",
    )


@app.post("/api/categorize")
async def categorize(current_user: dict = Depends(get_current_user)):
    """
    Run AI categorization on the logged-in user's stored transactions.
    """
    user_id = current_user["id"]
    transactions = load_transactions(user_id=user_id)
    if not transactions:
        raise HTTPException(status_code=404, detail="No transactions found. Upload a statement first.")

    categorized = await categorize_transactions(
        transactions,
        cache_lookup=lambda key: cache_lookup(key, user_id=user_id),
        cache_store=lambda key, cat, conf: cache_store(key, cat, conf, user_id=user_id),
    )

    save_transactions(categorized, user_id=user_id)
    logger.info(f"Categorized {len(categorized)} transactions for user {current_user['email']}")

    return {
        "categorized": len(categorized),
        "transactions": [t.model_dump(mode="json") for t in categorized],
    }


@app.get("/api/transactions")
async def get_transactions(current_user: dict = Depends(get_current_user)):
    """Return all transactions for the logged-in user."""
    user_id = current_user["id"]
    transactions = load_transactions(user_id=user_id)
    return {
        "count": len(transactions),
        "transactions": [t.model_dump(mode="json") for t in transactions],
    }


@app.get("/api/recurring", response_model=list[RecurringSubscription])
async def get_recurring(current_user: dict = Depends(get_current_user)):
    """Detect recurring subscription payments for the logged-in user."""
    user_id = current_user["id"]
    transactions = load_transactions(user_id=user_id)
    if not transactions:
        return []

    recurring = detect_recurring_payments(transactions)
    logger.info(f"Detected {len(recurring)} recurring subscriptions for user {current_user['email']}")
    return recurring


@app.get("/api/forecast", response_model=CashFlowForecast)
async def get_forecast(current_user: dict = Depends(get_current_user)):
    """Run cash-flow forecasting for the logged-in user."""
    user_id = current_user["id"]
    transactions = load_transactions(user_id=user_id)
    if not transactions:
        raise HTTPException(status_code=404, detail="No transactions found.")

    recurring = detect_recurring_payments(transactions)
    forecast = forecast_cash_flow(transactions, recurring)
    return forecast


@app.post("/api/override")
async def override_category(
    override: CategoryOverride,
    current_user: dict = Depends(get_current_user),
):
    """Manually override category for a transaction belonging to logged-in user."""
    user_id = current_user["id"]
    success = save_override(override.transaction_id, override.new_category.value, user_id=user_id)
    if not success:
        raise HTTPException(status_code=404, detail="Transaction not found or not owned by user.")

    return {"message": f"Category updated to '{override.new_category.value}'"}


@app.post("/api/chat", response_model=ChatQueryResponse)
async def chat_with_transactions(
    req: ChatQueryRequest,
    current_user: dict = Depends(get_current_user),
):
    """Ask natural language questions about user transactions."""
    user_id = current_user["id"]
    try:
        transactions = load_transactions(user_id=user_id)
        from backend.ai.assistant import answer_financial_query
        answer = answer_financial_query(req.query, transactions)
    except Exception as e:
        logger.error(f"Chat processing error: {e}")
        answer = f"Error analyzing transactions: {str(e)}"

    return ChatQueryResponse(
        query=req.query,
        answer=answer,
        timestamp=datetime.now().strftime("%I:%M %p"),
    )


@app.get("/api/summary", response_model=AnalysisSummary)
async def get_summary(current_user: dict = Depends(get_current_user)):
    """Return high-level analysis summary with health score for logged-in user."""
    user_id = current_user["id"]
    transactions = load_transactions(user_id=user_id)
    if not transactions:
        return AnalysisSummary(
            total_transactions=0,
            total_debits=0,
            total_credits=0,
            net_balance=0,
            categories_breakdown={},
            recurring_count=0,
        )

    total_debits = sum(t.amount for t in transactions if t.type == TransactionType.DEBIT)
    total_credits = sum(t.amount for t in transactions if t.type == TransactionType.CREDIT)

    cat_breakdown: dict[str, float] = {}
    for t in transactions:
        if t.type == TransactionType.DEBIT:
            cat_breakdown[t.category.value] = cat_breakdown.get(t.category.value, 0) + t.amount

    recurring = detect_recurring_payments(transactions)
    forecast = forecast_cash_flow(transactions, recurring)
    health = compute_financial_health_score(transactions)

    return AnalysisSummary(
        total_transactions=len(transactions),
        total_debits=round(total_debits, 2),
        total_credits=round(total_credits, 2),
        net_balance=round(total_credits - total_debits, 2),
        categories_breakdown={k: round(v, 2) for k, v in cat_breakdown.items()},
        recurring_count=len(recurring),
        forecast=forecast,
        health_score=health,
    )


@app.get("/api/intelligence-report", response_model=ExecutiveIntelligenceReport)
async def get_intelligence_report(current_user: dict = Depends(get_current_user)):
    """
    Generate comprehensive Precisa-style Executive Underwriting & Financial Health Report:
      • Financial Health Score (0 - 1000) & Risk Grade
      • 8+ Automated Risk, Fraud & Irregularity Checks
      • Top Counterparties (Inflow & Outflow)
      • Payment Channel / Mode Breakdown
      • Underwriting Verdict
    """
    user_id = current_user["id"]
    transactions = load_transactions(user_id=user_id)
    health = compute_financial_health_score(transactions)
    risk_checks = run_automated_risk_checks(transactions, health)
    top_counterparties, payment_modes = extract_counterparties_and_modes(transactions)

    # Monthly spend and income trends
    from collections import defaultdict
    monthly_stats = defaultdict(lambda: {"inflow": 0.0, "outflow": 0.0})
    for t in transactions:
        m_key = t.date.strftime("%b %Y")
        if t.type == TransactionType.CREDIT:
            monthly_stats[m_key]["inflow"] += t.amount
        else:
            monthly_stats[m_key]["outflow"] += t.amount

    monthly_trends = [
        {"month": k, "inflow": round(v["inflow"], 2), "outflow": round(v["outflow"], 2)}
        for k, v in monthly_stats.items()
    ]

    # Underwriting verdict calculation
    failed_critical = sum(1 for c in risk_checks if not c.passed and c.severity in (RiskSeverity.HIGH, RiskSeverity.CRITICAL))
    if health.overall_score >= 750 and failed_critical == 0:
        verdict = "🟢 Strong Financial Profile — Recommended for low-risk tier approvals and premium credit limits."
    elif health.overall_score >= 600 and failed_critical <= 1:
        verdict = "🟡 Moderate Profile — Standard risk criteria met. Minor anomalies noted in cash-flow buffer."
    else:
        verdict = "🔴 High-Risk Profile — Multiple risk triggers detected. Recommend manual underwriter review and collateral verification."

    return ExecutiveIntelligenceReport(
        health_score=health,
        risk_checks=risk_checks,
        top_counterparties=top_counterparties,
        payment_mode_breakdown=payment_modes,
        monthly_trends=monthly_trends,
        underwriting_verdict=verdict,
    )



@app.post("/api/sample-data")
async def load_sample_data(current_user: dict = Depends(get_current_user)):
    """Load sample data scoped directly to the logged-in user."""
    user_id = current_user["id"]
    sample_path = PROJECT_ROOT / "data" / "sample_statement.csv"
    if not sample_path.exists():
        raise HTTPException(status_code=404, detail="Sample data file not found.")

    # Clear existing data for this user
    clear_transactions(user_id=user_id)

    with open(sample_path, "r") as f:
        content = f.read()

    transactions = parse_csv(content)
    if not transactions:
        raise HTTPException(status_code=500, detail="Failed to parse sample data.")

    for t in transactions:
        t.user_id = user_id

    categorized = await categorize_transactions(
        transactions,
        cache_lookup=lambda key: cache_lookup(key, user_id=user_id),
        cache_store=lambda key, cat, conf: cache_store(key, cat, conf, user_id=user_id),
    )
    saved = save_transactions(categorized, user_id=user_id)

    logger.info(f"Loaded and categorized {saved} sample transactions for user {current_user['email']}")
    return UploadResponse(
        transactions_parsed=saved,
        message=f"Loaded {saved} sample transactions with AI categorization",
    )


@app.delete("/api/clear")
async def clear_data(current_user: dict = Depends(get_current_user)):
    """Clear all stored data for the logged-in user."""
    user_id = current_user["id"]
    clear_transactions(user_id=user_id)
    return {"message": "All user data cleared successfully."}


# ─── Health check ─────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "healthy", "version": "1.0.0"}

