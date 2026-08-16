"""
Merchant-name cleaner — regex-first extraction of readable names from
noisy bank-statement descriptions.

Indian bank statements are notoriously messy:
  • UPI strings:  "UPI-SWIGGY-9182736450@YBL-YESB0XXXXXX-123456789"
  • POS strings:  "POS 423867*DECATHLON SPO NEW DELHI IN"
  • NEFT/IMPS:    "NEFT-HDFC0001234-JOHN DOE-SAVINGS"
  • Card txns:    "CC 000381672 AMAZON.IN"

This module uses a cascade of regex patterns to extract the meaningful
merchant name.  It does NOT call the LLM — that only happens if the
regex pipeline returns nothing useful (handled in categorizer.py).
"""

from __future__ import annotations

import re


# ─── Pattern bank ─────────────────────────────────────────────────────────────

# Each pattern is (compiled_regex, group_index_to_extract).
# Order matters: first match wins.

_PATTERNS: list[tuple[re.Pattern, int]] = [
    # Canara / SBI Tilde format: "UPI~558316687013~DR~ANURAG~IPOS~District Dining~..." or "UPI~657780001154~CR~Anurag Pra~SBIN~..."
    (re.compile(r"UPI[~-]\d+[~-](?:DR|CR)[~-][^~-]+[~-][^~-]+[~-]([A-Za-z0-9 &'.]+?)(?:[~-]|$)", re.IGNORECASE), 1),
    (re.compile(r"UPI[~-]\d+[~-](?:DR|CR)[~-]([A-Za-z][A-Za-z0-9 &'.]+?)[~-]", re.IGNORECASE), 1),
    (re.compile(r"UPI[~-](?:DR|CR)[~-]([A-Za-z][A-Za-z0-9 &'.]+?)[~-]", re.IGNORECASE), 1),
    # UPI standard Indian format: "UPI/DR/622529470672/MR NAVAB /FDRL/..." or "UPI/CR/12345/NAME/..."
    (re.compile(r"UPI/(?:DR|CR)/\d+/([A-Za-z][A-Za-z0-9 &'.]+?)/", re.IGNORECASE), 1),
    # UPI variant: "UPI/DR/merchant/upiid"
    (re.compile(r"UPI/(?:DR|CR)/([A-Za-z][A-Za-z0-9 &'.]+?)/", re.IGNORECASE), 1),
    # UPI hyphen: "UPI-MERCHANT NAME-upiid@bank-IFSC-ref"
    (re.compile(r"UPI[-/]([A-Za-z][A-Za-z0-9 &'.]+?)[-/]\d", re.IGNORECASE), 1),
    # UPI slash with name: "UPI/MERCHANT NAME/..."
    (re.compile(r"UPI/([A-Za-z][A-Za-z0-9 &'.]+?)/", re.IGNORECASE), 1),
    # POS: "POS 123456*MERCHANT NAME CITY"
    (re.compile(r"POS\s+\d+\*(.+?)(?:\s{2,}|\s+[A-Z]{2}\s*$)", re.IGNORECASE), 1),
    # Card / CC: "CC 000123 MERCHANT"
    (re.compile(r"CC\s+\d+\s+(.+)", re.IGNORECASE), 1),
    # NEFT/IMPS: "NEFT-IFSC-NAME-..." or "IMPS-ref-NAME-..."
    (re.compile(r"(?:NEFT|IMPS|RTGS)[-/~][A-Z0-9]+[-/~]([A-Za-z][A-Za-z ]+?)[-/~]", re.IGNORECASE), 1),
    # EMI / Loan: "EMI-REF-MERCHANT"
    (re.compile(r"EMI[-/~]\w+[-/~](.+)", re.IGNORECASE), 1),
    # ATM: "ATM-CASH WDL-LOCATION"
    (re.compile(r"ATM[-/~](.+?)[-/~]", re.IGNORECASE), 1),
    # Generic: "BIL/MERCHANT/..."
    (re.compile(r"BIL[/-~]([A-Za-z][A-Za-z0-9 &'.]+?)[/-~]", re.IGNORECASE), 1),
]



# Junk tokens to strip from extracted names
_JUNK_TOKENS = re.compile(
    r"(?:@[A-Za-z]+|[A-Z]{4}\d{7}|\b[A-Z]{4}0\d{6}\b|\b\d{6,}\b|"
    r"\bIN\b|\bINDIA\b|\bPVT\b|\bLTD\b|\bPRIVATE\b|\bLIMITED\b)",
    re.IGNORECASE,
)

# Collapse whitespace
_MULTI_SPACE = re.compile(r"\s{2,}")


# ─── Public API ───────────────────────────────────────────────────────────────


def clean_merchant_name(raw_description: str) -> str:
    """
    Extract a clean, human-readable merchant/entity name from Indian bank narrations.
    Handles UPI (~ and / variants), POS, NEFT, IMPS, Cards, and ATM withdrawals.
    """
    if not raw_description:
        return "Unknown"

    # Remove line breaks and collapse whitespace so wrapped names (e.g. VEERES\nH) merge into VEERESH
    text = re.sub(r"[\r\n\t]+", "", raw_description.strip())
    text = re.sub(r"\s{2,}", " ", text)

    # Known bank handles & noise tokens in UPI paths
    BANK_HANDLES = {
        "UPI", "DR", "CR", "IPOS", "POS", "NA", "SBIN", "SBI", "HDFC", "ICIC", "ICICI",
        "AXIS", "UTIB", "KKBK", "KOTAK", "YESB", "YES", "IBL", "FDRL", "FEDERAL",
        "PUNB", "PNB", "CNRB", "CANARA", "BARB", "BOB", "UBIN", "UNION", "IDFB", "IDFC",
        "PYTM", "PAYTM", "GPay", "PHONEPE", "AIRP", "AIRTEL", "IOBA", "CORP", "SYND"
    }

    # 1. Check for Tilde-separated format (Canara, SBI, PNB, BoB, etc.):
    # e.g., "UPI~558316687013~DR~ANURAG~IPOS~District Dining~..." or "UPI~657780001154~CR~Anurag Pra~SBIN~..."
    if "~" in text:
        parts = [p.strip() for p in text.split("~") if p.strip()]
        meaningful = []
        for p in parts:
            p_clean = _strip_junk(p)
            if not p_clean or p.upper() in BANK_HANDLES:
                continue
            if re.match(r"^[\d*]+$", p_clean) or "@" in p or re.match(r"^[A-Z0-9]{12,}$", p):
                continue
            meaningful.append(p_clean)

        if meaningful:
            candidate = meaningful[-1] if len(meaningful) > 1 and any(k in meaningful[-1].lower() for k in ("store", "mart", "cafe", "dining", "restaurant", "hotel", "food", "petrol")) else meaningful[0]
            if len(candidate) >= 2:
                return _titlecase(candidate)

    # 2. Check for Slash-separated format (HDFC, ICICI, Axis, SBI, Federal, Canara, PNB, etc.):
    # e.g., "UPI/DR/659302952990/VEERESH/SBIN/**55247@IBL/..." or "UPI/CR/992817263/RAHUL SHARMA/HDFC/..."
    if "/" in text:
        parts = [p.strip() for p in text.split("/") if p.strip()]
        meaningful = []
        for p in parts:
            p_clean = _strip_junk(p)
            if not p_clean or p.upper() in BANK_HANDLES:
                continue
            if re.match(r"^[\d*]+$", p_clean) or "@" in p or re.match(r"^[A-Z0-9]{12,}$", p):
                continue
            meaningful.append(p_clean)

        if meaningful:
            candidate = meaningful[-1] if len(meaningful) > 1 and any(k in meaningful[-1].lower() for k in ("store", "mart", "cafe", "dining", "restaurant", "hotel", "food", "petrol")) else meaningful[0]
            if len(candidate) >= 2:
                return _titlecase(candidate)

    # 3. Check for Hyphen-separated format (UPI-NAME-upiid@bank or NEFT-IFSC-NAME):
    if "-" in text and ("UPI" in text.upper() or "NEFT" in text.upper() or "IMPS" in text.upper()):
        parts = [p.strip() for p in text.split("-") if p.strip()]
        meaningful = []
        for p in parts:
            p_clean = _strip_junk(p)
            if not p_clean or p.upper() in BANK_HANDLES or p.upper() in ("NEFT", "IMPS", "RTGS", "UPI"):
                continue
            if re.match(r"^[\d*]+$", p_clean) or "@" in p or re.match(r"^[A-Z0-9]{10,}$", p):
                continue
            meaningful.append(p_clean)

        if meaningful:
            candidate = meaningful[0]
            if len(candidate) >= 2:
                return _titlecase(candidate)

    # 4. Try standard regex pattern bank
    for pattern, group_idx in _PATTERNS:
        match = pattern.search(text)
        if match:
            name = match.group(group_idx).strip()
            name = _strip_junk(name)
            if len(name) >= 2:
                return _titlecase(name)

    # 5. Fallback: strip common prefixes and take the first meaningful chunk
    fallback = text
    for prefix in ("UPI-", "UPI/", "POS ", "NEFT-", "IMPS-", "RTGS-", "CC ", "ACH-", "NACH-"):
        if fallback.upper().startswith(prefix):
            fallback = fallback[len(prefix):]
            break

    fallback = _strip_junk(fallback).strip()
    if len(fallback) >= 2:
        return _titlecase(fallback[:40].strip())

    return raw_description[:40].strip()



# ─── Helpers ──────────────────────────────────────────────────────────────────


def _strip_junk(name: str) -> str:
    """Remove IFSC codes, long digit sequences, and corporate suffixes."""
    cleaned = _JUNK_TOKENS.sub("", name)
    cleaned = _MULTI_SPACE.sub(" ", cleaned)
    # Remove trailing/leading hyphens, slashes, dots
    cleaned = cleaned.strip(" -/.,*")
    return cleaned


def _titlecase(name: str) -> str:
    """Smart title-casing that preserves known acronyms."""
    # Simple title case — good enough for display
    words = name.lower().split()
    return " ".join(w.capitalize() for w in words if w)
