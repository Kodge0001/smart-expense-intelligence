"""
AI-powered transaction categorizer with multi-provider LLM support,
batching, caching, retry logic, and rule-based fallback.

WHY AI IS USED HERE (and not in recurring/forecast):
─────────────────────────────────────────────────────
Transaction descriptions are noisy, inconsistent, and vary wildly across
banks, payment gateways, and merchants.  A deterministic rule engine would
need hundreds of regex rules and still miss novel merchants.  An LLM
generalizes naturally from the merchant name + amount context.

COST CONTROL STRATEGY:
  1. Batch 10–20 transactions per API call (not one call per row).
  2. Cache results per merchant name in SQLite — each unique merchant
     triggers at most ONE API call ever.
  3. Rule-based fallback if no API key is set or if the API fails.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Optional

from dotenv import load_dotenv

from backend.ai.prompts import SYSTEM_PROMPT, build_categorization_prompt
from backend.models.schema import (
    Category,
    CategorizationBatchRequest,
    CategorizationResult,
    Transaction,
)

load_dotenv()
logger = logging.getLogger(__name__)

# Batch size for LLM API calls — balances cost vs. context window limits
BATCH_SIZE = 15


# ─── Rule-based fallback categorizer ─────────────────────────────────────────

# Specificity tiers with nuanced confidence scores
_KEYWORD_RULES: dict[str, tuple[Category, float]] = {
    # Subscriptions & Digital Services (High confidence recognizable brands: 0.92 - 0.98)
    "netflix": (Category.SUBSCRIPTIONS, 0.98),
    "spotify": (Category.SUBSCRIPTIONS, 0.98),
    "hotstar": (Category.SUBSCRIPTIONS, 0.95),
    "disney": (Category.SUBSCRIPTIONS, 0.95),
    "prime membership": (Category.SUBSCRIPTIONS, 0.96),
    "prime video": (Category.SUBSCRIPTIONS, 0.96),
    "amazon prime": (Category.SUBSCRIPTIONS, 0.96),
    "youtube premium": (Category.SUBSCRIPTIONS, 0.95),
    "youtube": (Category.SUBSCRIPTIONS, 0.92),
    "gym membership": (Category.SUBSCRIPTIONS, 0.92),
    "cultfit": (Category.SUBSCRIPTIONS, 0.94),
    "cult.fit": (Category.SUBSCRIPTIONS, 0.94),
    "apple.com/bill": (Category.SUBSCRIPTIONS, 0.95),
    "apple.com": (Category.SUBSCRIPTIONS, 0.92),
    "google play": (Category.SUBSCRIPTIONS, 0.92),
    "google storage": (Category.SUBSCRIPTIONS, 0.92),
    "chatgpt": (Category.SUBSCRIPTIONS, 0.95),
    "openai": (Category.SUBSCRIPTIONS, 0.95),
    "claude": (Category.SUBSCRIPTIONS, 0.92),
    "adobe": (Category.SUBSCRIPTIONS, 0.92),
    "canva": (Category.SUBSCRIPTIONS, 0.92),
    "subscription": (Category.SUBSCRIPTIONS, 0.88),
    "membership": (Category.SUBSCRIPTIONS, 0.85),
    "autopay": (Category.SUBSCRIPTIONS, 0.82),

    # Travel, Commute & Bookings (Flights, Trains, Hotels, Cabs, Events: 0.85 - 0.96)
    "bookmyshow": (Category.ENTERTAINMENT, 0.96),
    "pvr": (Category.ENTERTAINMENT, 0.95),
    "inox": (Category.ENTERTAINMENT, 0.95),
    "cinepolis": (Category.ENTERTAINMENT, 0.94),
    "cinema": (Category.ENTERTAINMENT, 0.90),
    "movie": (Category.ENTERTAINMENT, 0.88),
    "event": (Category.ENTERTAINMENT, 0.85),
    "makemytrip": (Category.TRAVEL, 0.96),
    "goibibo": (Category.TRAVEL, 0.95),
    "easemytrip": (Category.TRAVEL, 0.95),
    "cleartrip": (Category.TRAVEL, 0.95),
    "yatra": (Category.TRAVEL, 0.94),
    "irctc": (Category.TRAVEL, 0.96),
    "redbus": (Category.TRAVEL, 0.95),
    "abhibus": (Category.TRAVEL, 0.94),
    "oyo": (Category.TRAVEL, 0.94),
    "airbnb": (Category.TRAVEL, 0.95),
    "agoda": (Category.TRAVEL, 0.95),
    "booking.com": (Category.TRAVEL, 0.95),
    "indigo": (Category.TRAVEL, 0.96),
    "air india": (Category.TRAVEL, 0.96),
    "spicejet": (Category.TRAVEL, 0.95),
    "akasa": (Category.TRAVEL, 0.95),
    "vistara": (Category.TRAVEL, 0.96),
    "flight": (Category.TRAVEL, 0.92),
    "airline": (Category.TRAVEL, 0.92),
    "hotel booking": (Category.TRAVEL, 0.92),
    "resort": (Category.TRAVEL, 0.90),
    "uber": (Category.TRAVEL, 0.95),
    "ola": (Category.TRAVEL, 0.95),
    "rapido": (Category.TRAVEL, 0.95),
    "petrol": (Category.TRAVEL, 0.94),
    "indian oil": (Category.TRAVEL, 0.95),
    "hp petrol": (Category.TRAVEL, 0.95),
    "bharat petroleum": (Category.TRAVEL, 0.95),
    "iocl": (Category.TRAVEL, 0.94),
    "bpcl": (Category.TRAVEL, 0.94),
    "fuel": (Category.TRAVEL, 0.92),
    "cng": (Category.TRAVEL, 0.92),
    "diesel": (Category.TRAVEL, 0.92),
    "metro": (Category.TRAVEL, 0.92),
    "toll": (Category.TRAVEL, 0.92),
    "fastag": (Category.TRAVEL, 0.95),
    "cab": (Category.TRAVEL, 0.88),
    "auto": (Category.TRAVEL, 0.85),
    "bus": (Category.TRAVEL, 0.88),
    "parking": (Category.TRAVEL, 0.88),
    "train": (Category.TRAVEL, 0.90),
    "railway": (Category.TRAVEL, 0.92),

    # Utilities & Recharges (High confidence telecom/utilities: 0.90 - 0.95)
    "jio fiber": (Category.UTILITIES, 0.95),
    "jio": (Category.UTILITIES, 0.92),
    "broadband-autopay": (Category.UTILITIES, 0.94),
    "act fibernet": (Category.UTILITIES, 0.95),
    "airtel": (Category.UTILITIES, 0.92),
    "electricity": (Category.UTILITIES, 0.93),
    "gas": (Category.UTILITIES, 0.91),
    "water": (Category.UTILITIES, 0.90),
    "mobile recharge": (Category.UTILITIES, 0.90),
    "recharge": (Category.UTILITIES, 0.88),
    "bsnl": (Category.UTILITIES, 0.88),
    "vi ": (Category.UTILITIES, 0.86),
    "bescom": (Category.UTILITIES, 0.94),
    "tneb": (Category.UTILITIES, 0.94),
    "mahadiscom": (Category.UTILITIES, 0.94),

    # Food & Dining (0.85 - 0.95)
    "swiggy": (Category.FOOD, 0.95),
    "zomato": (Category.FOOD, 0.95),
    "blinkit": (Category.FOOD, 0.94),
    "zepto": (Category.FOOD, 0.94),
    "bigbasket": (Category.FOOD, 0.93),
    "instamart": (Category.FOOD, 0.94),
    "starbucks": (Category.FOOD, 0.92),
    "mcdonalds": (Category.FOOD, 0.92),
    "dominos": (Category.FOOD, 0.92),
    "kfc": (Category.FOOD, 0.90),
    "subway": (Category.FOOD, 0.90),
    "burger king": (Category.FOOD, 0.92),
    "pizza hut": (Category.FOOD, 0.90),
    "restaurant": (Category.FOOD, 0.88),
    "cafe": (Category.FOOD, 0.88),
    "bakery": (Category.FOOD, 0.86),
    "bakes": (Category.FOOD, 0.86),
    "grocery": (Category.FOOD, 0.85),
    "supermarket": (Category.FOOD, 0.85),
    "biryani": (Category.FOOD, 0.88),
    "food": (Category.FOOD, 0.85),
    "fruit": (Category.FOOD, 0.88),
    "juice": (Category.FOOD, 0.88),
    "tea": (Category.FOOD, 0.86),
    "chai": (Category.FOOD, 0.86),
    "coffee": (Category.FOOD, 0.86),
    "hotel": (Category.FOOD, 0.82),
    "sagar": (Category.FOOD, 0.88),
    "sweets": (Category.FOOD, 0.88),
    "canteen": (Category.FOOD, 0.86),
    "snacks": (Category.FOOD, 0.86),
    "tiffin": (Category.FOOD, 0.88),
    "mess": (Category.FOOD, 0.88),
    "kitchen": (Category.FOOD, 0.86),
    "corner": (Category.FOOD, 0.82),
    "express": (Category.FOOD, 0.80),
    "pizza": (Category.FOOD, 0.90),
    "burger": (Category.FOOD, 0.90),
    "momos": (Category.FOOD, 0.88),
    "rolls": (Category.FOOD, 0.88),
    "shawarma": (Category.FOOD, 0.88),
    "meals": (Category.FOOD, 0.86),
    "bhojanalaya": (Category.FOOD, 0.88),
    "dhaba": (Category.FOOD, 0.88),
    "bhat": (Category.FOOD, 0.82),
    "veg": (Category.FOOD, 0.82),
    "nonveg": (Category.FOOD, 0.82),
    "dosa": (Category.FOOD, 0.88),
    "idli": (Category.FOOD, 0.88),
    "dining": (Category.FOOD, 0.90),
    "bhojanam": (Category.FOOD, 0.88),
    "rasoi": (Category.FOOD, 0.88),
    "grand": (Category.FOOD, 0.82),
    "paratha": (Category.FOOD, 0.88),
    "sandwich": (Category.FOOD, 0.88),
    "ice cream": (Category.FOOD, 0.90),
    "juice centre": (Category.FOOD, 0.90),
    "bar": (Category.FOOD, 0.82),
    "beverage": (Category.FOOD, 0.85),
    "drink": (Category.FOOD, 0.82),
    "treats": (Category.FOOD, 0.85),
    "refreshment": (Category.FOOD, 0.85),

    # Shopping (0.80 - 0.95)
    "amazon": (Category.SHOPPING, 0.94),
    "flipkart": (Category.SHOPPING, 0.94),
    "myntra": (Category.SHOPPING, 0.93),
    "croma": (Category.SHOPPING, 0.92),
    "decathlon": (Category.SHOPPING, 0.93),
    "ajio": (Category.SHOPPING, 0.91),
    "reliance": (Category.SHOPPING, 0.88),
    "dmart": (Category.SHOPPING, 0.92),
    "clothing": (Category.SHOPPING, 0.85),
    "electronics": (Category.SHOPPING, 0.88),
    "mart": (Category.SHOPPING, 0.85),
    "store": (Category.SHOPPING, 0.82),
    "bazaar": (Category.SHOPPING, 0.85),
    "retail": (Category.SHOPPING, 0.82),
    "shop": (Category.SHOPPING, 0.80),
    "fashion": (Category.SHOPPING, 0.85),
    "footwear": (Category.SHOPPING, 0.85),
    "jewel": (Category.SHOPPING, 0.88),
    "stationery": (Category.SHOPPING, 0.85),
    "book": (Category.SHOPPING, 0.82),

    # Healthcare (0.85 - 0.95)
    "apollo": (Category.HEALTHCARE, 0.94),
    "1mg": (Category.HEALTHCARE, 0.94),
    "pharmeasy": (Category.HEALTHCARE, 0.93),
    "pharmacy": (Category.HEALTHCARE, 0.90),
    "hospital": (Category.HEALTHCARE, 0.92),
    "clinic": (Category.HEALTHCARE, 0.88),
    "medical": (Category.HEALTHCARE, 0.85),
    "chemist": (Category.HEALTHCARE, 0.88),
    "diagnostic": (Category.HEALTHCARE, 0.88),
    "lab": (Category.HEALTHCARE, 0.80),
    "doctor": (Category.HEALTHCARE, 0.88),
    "dental": (Category.HEALTHCARE, 0.88),
    "optical": (Category.HEALTHCARE, 0.85),
    "lenskart": (Category.HEALTHCARE, 0.94),

    # Rent & Housing
    "rent": (Category.RENT, 0.92),
    "landlord": (Category.RENT, 0.89),
    "society": (Category.RENT, 0.82),
    "maintenance": (Category.RENT, 0.80),
    "house": (Category.RENT, 0.78),

    # Transfers & P2P
    "neft": (Category.TRANSFERS, 0.90),
    "imps": (Category.TRANSFERS, 0.90),
    "rtgs": (Category.TRANSFERS, 0.90),
    "self transfer": (Category.TRANSFERS, 0.95),
    "transfer": (Category.TRANSFERS, 0.82),
    "sent to": (Category.TRANSFERS, 0.85),
    "paid to": (Category.TRANSFERS, 0.82),
    "pay to": (Category.TRANSFERS, 0.82),
    "upi/dr": (Category.TRANSFERS, 0.75),
    "upi/cr": (Category.TRANSFERS, 0.75),
    "mr ": (Category.TRANSFERS, 0.78),
    "mrs ": (Category.TRANSFERS, 0.78),
    "ms ": (Category.TRANSFERS, 0.78),
    "shri ": (Category.TRANSFERS, 0.78),

    # Salary & Income
    "salary": (Category.SALARY, 0.96),
    "payroll": (Category.SALARY, 0.95),
    "stipend": (Category.SALARY, 0.90),
    "interest": (Category.SALARY, 0.85),
    "dividend": (Category.SALARY, 0.88),
}


def _rule_based_categorize(merchant_name: str, amount: float, txn_type: str) -> CategorizationResult:
    """
    Deterministic fallback categorizer using keyword matching with calibrated confidence scores.
    Used when no LLM API key is configured or when the LLM fails.
    """
    lower = merchant_name.lower().replace("~", " ").replace("/", " ").replace("-", " ")

    # Salary heuristic: large credits
    if txn_type == "credit" and ("salary" in lower or "payroll" in lower or amount >= 25000):
        confidence = 0.92 if "salary" in lower else 0.78
        return CategorizationResult(
            transaction_id="",
            category=Category.SALARY,
            clean_merchant_name=merchant_name,
            confidence=confidence,
        )

    # Sort keywords by base confidence descending then length descending so high-confidence brand matches take precedence
    for keyword, (category, base_conf) in sorted(_KEYWORD_RULES.items(), key=lambda x: (x[1][1], len(x[0])), reverse=True):
        if keyword in lower:
            # Calibrate confidence based on exact match vs partial substring
            if lower.strip() == keyword:
                conf = min(0.99, base_conf + 0.03)
            else:
                conf = base_conf
            return CategorizationResult(
                transaction_id="",
                category=category,
                clean_merchant_name=merchant_name,
                confidence=round(conf, 2),
            )

    # Smart P2P & UPI Heuristic: If it has upi/transfer or person title (mr/ms/shri/pra/sbi/okaxis)
    if any(k in lower for k in ("upi", "neft", "imps", "rtgs", "cr", "dr", "sbin", "okaxis", "okhdfcbank", "okicici", "paytm", "gpay")):
        return CategorizationResult(
            transaction_id="",
            category=Category.TRANSFERS,
            clean_merchant_name=merchant_name,
            confidence=0.75,
        )

    return CategorizationResult(
        transaction_id="",
        category=Category.OTHER,
        clean_merchant_name=merchant_name,
        confidence=0.45,
    )




# ─── LLM provider abstraction ────────────────────────────────────────────────


def _get_llm_provider() -> Optional[str]:
    """Detect which LLM provider is configured via environment variables."""
    if os.getenv("OPENAI_API_KEY"):
        return "openai"
    if os.getenv("ANTHROPIC_API_KEY"):
        return "anthropic"
    if os.getenv("GOOGLE_API_KEY"):
        return "google"
    return None


def _call_openai(system_prompt: str, user_message: str) -> str:
    """Call OpenAI API and return the response text."""
    from openai import OpenAI
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
        temperature=0.1,
        max_tokens=4096,
    )
    return response.choices[0].message.content or ""


def _call_anthropic(system_prompt: str, user_message: str) -> str:
    """Call Anthropic API and return the response text."""
    import anthropic
    client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    model = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-20250514")
    response = client.messages.create(
        model=model,
        max_tokens=4096,
        system=system_prompt,
        messages=[{"role": "user", "content": user_message}],
    )
    return response.content[0].text


def _call_google(system_prompt: str, user_message: str) -> str:
    """Call Google Gemini API and return the response text."""
    key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not key:
        return ""
    import urllib.request
    import json
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3.5-flash:generateContent?key={key}"
    payload = {
        "contents": [{"parts": [{"text": f"{system_prompt}\n\n{user_message}"}]}],
        "generationConfig": {"temperature": 0.3, "maxOutputTokens": 1024},
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        res = json.loads(resp.read().decode("utf-8"))
        return res["candidates"][0]["content"]["parts"][0]["text"]


_LLM_CALLERS = {
    "openai": _call_openai,
    "anthropic": _call_anthropic,
    "google": _call_google,
}


def _call_llm(system_prompt: str, user_message: str) -> Optional[str]:
    """Call the configured LLM provider. Returns None if no provider is set."""
    provider = _get_llm_provider()
    if not provider:
        return None

    caller = _LLM_CALLERS[provider]
    try:
        return caller(system_prompt, user_message)
    except Exception as e:
        logger.error(f"LLM API call failed ({provider}): {e}")
        return None


# ─── JSON response parsing ───────────────────────────────────────────────────


def _parse_llm_response(response_text: str) -> list[dict]:
    """
    Parse the LLM's JSON response, handling common formatting issues.
    Returns a list of dicts or raises ValueError.
    """
    # Strip markdown code fences if present
    text = response_text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        # Remove first and last lines (``` markers)
        lines = [l for l in lines if not l.strip().startswith("```")]
        text = "\n".join(lines)

    parsed = json.loads(text)
    if not isinstance(parsed, list):
        raise ValueError("Expected JSON array")

    return parsed


# ─── Main categorization pipeline ────────────────────────────────────────────


async def categorize_transactions(
    transactions: list[Transaction],
    cache_lookup: callable = None,
    cache_store: callable = None,
) -> list[Transaction]:
    """
    Categorize a list of transactions using LLM (with caching & fallback).

    Pipeline:
      1. Check SQLite cache for each merchant name.
      2. Batch uncached merchants and send to LLM (10–15 per batch).
      3. Parse strict JSON response; retry once on failure.
      4. Fall back to rule-based categorizer if LLM unavailable/fails.
      5. Store new results in cache.

    Args:
        transactions: List of Transaction objects to categorize.
        cache_lookup: async fn(merchant_name) → CategorizationResult | None
        cache_store:  async fn(merchant_name, category, confidence) → None

    Returns:
        The same list with .category, .confidence, and .merchant_clean updated.
    """
    # Group transactions by merchant to avoid redundant categorizations
    merchant_groups: dict[str, list[Transaction]] = {}
    for txn in transactions:
        key = txn.merchant_clean.lower().strip()
        merchant_groups.setdefault(key, []).append(txn)

    # Step 1: Check cache
    uncached_merchants: list[tuple[str, Transaction]] = []
    for merchant_key, txns in merchant_groups.items():
        cached = None
        if cache_lookup:
            cached = await cache_lookup(merchant_key)

        if cached:
            # Apply cached result to all transactions with this merchant
            for txn in txns:
                txn.category = cached.category
                txn.confidence = cached.confidence
                txn.merchant_clean = cached.clean_merchant_name or txn.merchant_clean
        else:
            # Take the first txn as representative for LLM categorization
            uncached_merchants.append((merchant_key, txns[0]))

    if not uncached_merchants:
        return transactions

    # Step 2: Batch and categorize uncached merchants
    llm_results: dict[str, CategorizationResult] = {}

    # Try LLM first
    provider = _get_llm_provider()
    if provider:
        batches = [
            uncached_merchants[i:i + BATCH_SIZE]
            for i in range(0, len(uncached_merchants), BATCH_SIZE)
        ]

        for batch in batches:
            batch_request = [
                {
                    "transaction_id": txn.id,
                    "merchant_name": txn.merchant_clean,
                    "amount": txn.amount,
                    "type": txn.type.value,
                }
                for _, txn in batch
            ]

            user_message = build_categorization_prompt(batch_request)

            # Try LLM call with one retry
            for attempt in range(2):
                response_text = _call_llm(SYSTEM_PROMPT, user_message)
                if not response_text:
                    break

                try:
                    parsed = _parse_llm_response(response_text)
                    for item in parsed:
                        try:
                            result = CategorizationResult(
                                transaction_id=item.get("transaction_id", ""),
                                category=Category(item.get("category", "other")),
                                clean_merchant_name=item.get("clean_merchant_name", ""),
                                confidence=float(item.get("confidence", 0.5)),
                            )
                            # Map back to merchant key
                            for merchant_key, txn in batch:
                                if txn.id == result.transaction_id:
                                    llm_results[merchant_key] = result
                                    break
                        except (ValueError, KeyError):
                            continue
                    break  # Success — don't retry
                except (json.JSONDecodeError, ValueError) as e:
                    logger.warning(f"LLM response parse error (attempt {attempt + 1}): {e}")
                    if attempt == 0:
                        continue  # Retry once
                    # Fall through to rule-based

    # Step 3: Apply results (LLM or rule-based fallback)
    for merchant_key, representative_txn in uncached_merchants:
        if merchant_key in llm_results:
            result = llm_results[merchant_key]
        else:
            # Rule-based fallback (check cleaned name first, fallback to raw description)
            result = _rule_based_categorize(
                representative_txn.merchant_clean,
                representative_txn.amount,
                representative_txn.type.value,
            )
            if result.category == Category.OTHER and representative_txn.raw_description:
                result_raw = _rule_based_categorize(
                    representative_txn.raw_description,
                    representative_txn.amount,
                    representative_txn.type.value,
                )
                if result_raw.category != Category.OTHER:
                    result = result_raw

            result.transaction_id = representative_txn.id


        # Apply to all transactions with this merchant
        for txn in merchant_groups[merchant_key]:
            if not txn.is_user_override:  # Don't overwrite manual corrections
                txn.category = result.category
                txn.confidence = result.confidence
                if result.clean_merchant_name:
                    txn.merchant_clean = result.clean_merchant_name

        # Step 4: Cache the result
        if cache_store:
            await cache_store(merchant_key, result.category.value, result.confidence)

    return transactions
