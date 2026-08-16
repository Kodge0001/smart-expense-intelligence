"""
SQLite persistence layer for the Smart Expense Intelligence System.

Stores transactions, AI categorization cache, and user overrides.
Uses aiosqlite for async compatibility with FastAPI.
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
import uuid
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Optional


from backend.models.schema import (
    Category,
    CategorizationResult,
    Transaction,
    TransactionType,
)

logger = logging.getLogger(__name__)

# Database file location — relative to project root
DB_DIR = Path(__file__).resolve().parent.parent.parent / "data"
DB_PATH = DB_DIR / "expense_intelligence.db"


def _ensure_db_dir():
    """Ensure the data directory exists."""
    DB_DIR.mkdir(parents=True, exist_ok=True)


def get_connection() -> sqlite3.Connection:
    """Get a synchronous SQLite connection (used for simplicity)."""
    _ensure_db_dir()
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db():
    """Create database tables if they don't exist, and migrate columns if needed."""
    conn = get_connection()
    try:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY,
                email TEXT UNIQUE NOT NULL,
                full_name TEXT DEFAULT '',
                phone TEXT DEFAULT '',
                occupation TEXT DEFAULT '',
                monthly_budget REAL DEFAULT 0.0,
                currency TEXT DEFAULT 'INR',
                city TEXT DEFAULT '',
                bio TEXT DEFAULT '',
                created_at TEXT DEFAULT (datetime('now')),
                last_login TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS otp_verifications (
                email TEXT PRIMARY KEY,
                otp_code TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                attempts_count INTEGER DEFAULT 0,
                last_sent_at TEXT DEFAULT (datetime('now')),
                hourly_count INTEGER DEFAULT 1,
                hourly_window_start TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS transactions (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL DEFAULT 'default_user',
                date TEXT NOT NULL,
                raw_description TEXT NOT NULL,
                amount REAL NOT NULL,
                type TEXT NOT NULL,
                merchant_raw TEXT DEFAULT '',
                merchant_clean TEXT DEFAULT '',
                category TEXT DEFAULT 'uncategorized',
                confidence REAL DEFAULT 0.0,
                is_user_override INTEGER DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS category_cache (
                merchant_key TEXT PRIMARY KEY,
                user_id TEXT DEFAULT 'global',
                category TEXT NOT NULL,
                confidence REAL DEFAULT 0.5,
                clean_name TEXT DEFAULT '',
                created_at TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS overrides (
                transaction_id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL DEFAULT 'default_user',
                old_category TEXT,
                new_category TEXT NOT NULL,
                merchant_key TEXT,
                created_at TEXT DEFAULT (datetime('now'))
            );
        """)

        # Backward compatibility migration: ensure user_id column exists
        columns = [row["name"] for row in conn.execute("PRAGMA table_info(transactions)").fetchall()]
        if "user_id" not in columns:
            conn.execute("ALTER TABLE transactions ADD COLUMN user_id TEXT NOT NULL DEFAULT 'default_user'")

        override_columns = [row["name"] for row in conn.execute("PRAGMA table_info(overrides)").fetchall()]
        if "user_id" not in override_columns:
            conn.execute("ALTER TABLE overrides ADD COLUMN user_id TEXT NOT NULL DEFAULT 'default_user'")

        cache_columns = [row["name"] for row in conn.execute("PRAGMA table_info(category_cache)").fetchall()]
        if "user_id" not in cache_columns:
            conn.execute("ALTER TABLE category_cache ADD COLUMN user_id TEXT DEFAULT 'global'")

        conn.executescript("""
            CREATE INDEX IF NOT EXISTS idx_txn_user_date ON transactions(user_id, date);
            CREATE INDEX IF NOT EXISTS idx_txn_user_merchant ON transactions(user_id, merchant_clean);
            CREATE INDEX IF NOT EXISTS idx_cache_merchant ON category_cache(merchant_key);
        """)


        conn.commit()
    finally:
        conn.close()



# ─── User & OTP CRUD ─────────────────────────────────────────────────────────


def get_or_create_user(email: str) -> dict:
    """Fetch user by email or create a new user account."""
    email_clean = email.lower().strip()
    conn = get_connection()
    try:
        row = conn.execute("SELECT * FROM users WHERE email = ?", (email_clean,)).fetchone()
        now = datetime.now(timezone.utc).isoformat()
        if row:
            conn.execute("UPDATE users SET last_login = ? WHERE id = ?", (now, row["id"]))
            conn.commit()
            return dict(row)

        user_id = str(uuid.uuid4())
        conn.execute(
            "INSERT INTO users (id, email, created_at, last_login) VALUES (?, ?, ?, ?)",
            (user_id, email_clean, now, now),
        )
        conn.commit()
        return {
            "id": user_id,
            "email": email_clean,
            "created_at": now,
            "last_login": now,
        }
    finally:
        conn.close()


def get_user_by_email(email: str) -> Optional[dict]:
    """Fetch user record by email without creating one."""
    email_clean = email.lower().strip()
    conn = get_connection()
    try:
        row = conn.execute("SELECT * FROM users WHERE email = ?", (email_clean,)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def get_user_by_id(user_id: str) -> Optional[dict]:
    """Fetch user record by ID."""
    conn = get_connection()
    try:
        row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def update_user_profile(user_id: str, profile_data: dict) -> Optional[dict]:
    """Update user profile details."""
    conn = get_connection()
    try:
        # Build update query dynamically for provided keys
        allowed_fields = {"full_name", "phone", "occupation", "monthly_budget", "currency", "city", "bio"}
        updates = {k: v for k, v in profile_data.items() if k in allowed_fields and v is not None}
        if not updates:
            return get_user_by_id(user_id)

        set_clauses = ", ".join([f"{k} = ?" for k in updates.keys()])
        values = list(updates.values()) + [user_id]
        conn.execute(f"UPDATE users SET {set_clauses} WHERE id = ?", tuple(values))
        conn.commit()
        return get_user_by_id(user_id)
    finally:
        conn.close()


def _ensure_profile_columns():
    """Ensure newly introduced profile columns exist in users table."""
    conn = get_connection()
    try:
        cursor = conn.execute("PRAGMA table_info(users)")
        existing_cols = {row["name"] for row in cursor.fetchall()}
        cols_to_add = {
            "full_name": "TEXT DEFAULT ''",
            "phone": "TEXT DEFAULT ''",
            "occupation": "TEXT DEFAULT ''",
            "monthly_budget": "REAL DEFAULT 0.0",
            "currency": "TEXT DEFAULT 'INR'",
            "city": "TEXT DEFAULT ''",
            "bio": "TEXT DEFAULT ''",
        }
        for col, col_type in cols_to_add.items():
            if col not in existing_cols:
                try:
                    conn.execute(f"ALTER TABLE users ADD COLUMN {col} {col_type}")
                except Exception:
                    pass
        conn.commit()
    finally:
        conn.close()


_ensure_profile_columns()



def save_otp(email: str, otp_code: str) -> tuple[bool, str]:
    """
    Store or update 6-digit OTP for email with rate-limiting.
    Enforces:
      - Max 1 OTP per 60 seconds
      - Max 5 OTPs per hour window
      - 5-minute expiration
    Returns (success, message).
    """
    email_clean = email.lower().strip()
    now_dt = datetime.now(timezone.utc)
    expires_dt = now_dt + timedelta(minutes=5)
    now_str = now_dt.isoformat()
    expires_str = expires_dt.isoformat()


    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM otp_verifications WHERE email = ?", (email_clean,)
        ).fetchone()

        if row:
            last_sent = datetime.fromisoformat(row["last_sent_at"])
            window_start = datetime.fromisoformat(row["hourly_window_start"])

            # 60s cooldown check
            if (now_dt - last_sent).total_seconds() < 60:
                wait_sec = int(60 - (now_dt - last_sent).total_seconds())
                return False, f"Please wait {wait_sec}s before requesting a new code."

            # Hourly rate limit (max 5 per hour)
            if (now_dt - window_start).total_seconds() < 3600:
                if row["hourly_count"] >= 5:
                    return False, "Rate limit exceeded. Maximum 5 OTP requests per hour."
                new_hourly_count = row["hourly_count"] + 1
                new_window_start = row["hourly_window_start"]
            else:
                new_hourly_count = 1
                new_window_start = now_str

            conn.execute(
                """UPDATE otp_verifications
                   SET otp_code = ?, expires_at = ?, attempts_count = 0,
                       last_sent_at = ?, hourly_count = ?, hourly_window_start = ?
                   WHERE email = ?""",
                (otp_code, expires_str, now_str, new_hourly_count, new_window_start, email_clean),
            )
        else:
            conn.execute(
                """INSERT INTO otp_verifications
                   (email, otp_code, expires_at, attempts_count, last_sent_at, hourly_count, hourly_window_start)
                   VALUES (?, ?, ?, 0, ?, 1, ?)""",
                (email_clean, otp_code, expires_str, now_str, now_str),
            )

        conn.commit()
        return True, "OTP generated and ready to send."
    finally:
        conn.close()


def verify_otp(email: str, entered_otp: str) -> tuple[bool, str]:
    """
    Verify OTP entered by user.
    Enforces:
      - Expiration within 10 minutes
      - Maximum 5 attempts per generated OTP
    Returns (success, message).
    """
    email_clean = email.lower().strip()
    now_dt = datetime.now(timezone.utc)

    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM otp_verifications WHERE email = ?", (email_clean,)
        ).fetchone()

        if not row:
            return False, "No OTP request found for this email. Please request a new code."

        if row["attempts_count"] >= 5:
            return False, "Maximum verification attempts exceeded. Please request a new code."

        expires_dt = datetime.fromisoformat(row["expires_at"])
        if now_dt > expires_dt:
            return False, "The code has expired (10-minute limit). Please request a new code."

        if row["otp_code"].strip() != entered_otp.strip():
            conn.execute(
                "UPDATE otp_verifications SET attempts_count = attempts_count + 1 WHERE email = ?",
                (email_clean,),
            )
            conn.commit()
            remaining = 5 - (row["attempts_count"] + 1)
            return False, f"Incorrect code. {remaining} attempt(s) remaining."

        # Success - clean up OTP
        conn.execute("DELETE FROM otp_verifications WHERE email = ?", (email_clean,))
        conn.commit()
        return True, "OTP verified successfully."
    finally:
        conn.close()


# ─── Transaction CRUD (Scoped to User) ───────────────────────────────────────


def save_transactions(transactions: list[Transaction], user_id: str = "default_user") -> int:
    """Save or update transactions scoped to a specific user."""
    conn = get_connection()
    try:
        for txn in transactions:
            conn.execute(
                """INSERT OR REPLACE INTO transactions
                   (id, user_id, date, raw_description, amount, type, merchant_raw,
                    merchant_clean, category, confidence, is_user_override)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    txn.id,
                    user_id,
                    txn.date.isoformat(),
                    txn.raw_description,
                    txn.amount,
                    txn.type.value,
                    txn.merchant_raw,
                    txn.merchant_clean,
                    txn.category.value,
                    txn.confidence,
                    1 if txn.is_user_override else 0,
                ),
            )
        conn.commit()
        return len(transactions)
    finally:
        conn.close()


def load_transactions(user_id: str = "default_user") -> list[Transaction]:
    """Load all transactions scoped to a specific user."""
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM transactions WHERE user_id = ? ORDER BY date DESC",
            (user_id,),
        ).fetchall()

        return [
            Transaction(
                id=row["id"],
                user_id=row["user_id"],
                date=date.fromisoformat(row["date"][:10]) if "T" in row["date"] or len(row["date"]) > 10 else date.fromisoformat(row["date"]),
                raw_description=row["raw_description"],
                amount=row["amount"],
                type=TransactionType(row["type"]),
                merchant_raw=row["merchant_raw"],
                merchant_clean=row["merchant_clean"],
                category=Category(row["category"]),
                confidence=row["confidence"],
                is_user_override=bool(row["is_user_override"]),
            )
            for row in rows
        ]
    finally:
        conn.close()


def clear_transactions(user_id: str = "default_user"):
    """Delete all transactions for a specific user."""
    conn = get_connection()
    try:
        conn.execute("DELETE FROM transactions WHERE user_id = ?", (user_id,))
        conn.commit()
    finally:
        conn.close()


# ─── Category Cache ──────────────────────────────────────────────────────────


async def cache_lookup(merchant_key: str, user_id: str = "default_user") -> Optional[CategorizationResult]:
    """Look up cached categorization for a merchant (checks user cache or global cache)."""
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM category_cache WHERE merchant_key = ? AND (user_id = ? OR user_id = 'global') ORDER BY user_id DESC LIMIT 1",
            (merchant_key.lower().strip(), user_id),
        ).fetchone()

        if row:
            return CategorizationResult(
                transaction_id="",
                category=Category(row["category"]),
                clean_merchant_name=row["clean_name"] or merchant_key,
                confidence=row["confidence"],
            )
        return None
    finally:
        conn.close()


async def cache_store(merchant_key: str, category: str, confidence: float, user_id: str = "default_user"):
    """Store a categorization result in cache."""
    conn = get_connection()
    try:
        conn.execute(
            """INSERT OR REPLACE INTO category_cache
               (merchant_key, user_id, category, confidence, clean_name)
               VALUES (?, ?, ?, ?, ?)""",
            (merchant_key.lower().strip(), user_id, category, confidence, merchant_key),
        )
        conn.commit()
    finally:
        conn.close()


# ─── User Overrides ──────────────────────────────────────────────────────────


def save_override(transaction_id: str, new_category: str, user_id: str = "default_user") -> bool:
    """Save a user's category override for a transaction and update cache."""
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM transactions WHERE id = ? AND user_id = ?",
            (transaction_id, user_id),
        ).fetchone()

        if not row:
            return False

        old_category = row["category"]
        merchant_key = row["merchant_clean"].lower().strip()

        conn.execute(
            """INSERT OR REPLACE INTO overrides
               (transaction_id, user_id, old_category, new_category, merchant_key)
               VALUES (?, ?, ?, ?, ?)""",
            (transaction_id, user_id, old_category, new_category, merchant_key),
        )

        conn.execute(
            """UPDATE transactions
               SET category = ?, is_user_override = 1, confidence = 1.0
               WHERE id = ? AND user_id = ?""",
            (new_category, transaction_id, user_id),
        )

        conn.execute(
            """INSERT OR REPLACE INTO category_cache
               (merchant_key, user_id, category, confidence, clean_name)
               VALUES (?, ?, ?, 1.0, ?)""",
            (merchant_key, user_id, new_category, row["merchant_clean"]),
        )

        conn.commit()
        return True
    finally:
        conn.close()

