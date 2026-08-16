"""
Statement parser — converts CSV and PDF bank statements into structured
Transaction objects.

Supports common Indian bank CSV formats (varied header names) and basic
PDF text extraction with regex-based table parsing.
"""

from __future__ import annotations

import csv
import io
import re
from datetime import date, datetime
from typing import BinaryIO

from pypdf import PdfReader

from backend.ingestion.cleaner import clean_merchant_name
from backend.models.schema import Transaction, TransactionType



# ─── CSV Parsing ──────────────────────────────────────────────────────────────

# Mapping of common header variations to canonical names
_HEADER_MAP: dict[str, str] = {
    # Date
    "date": "date",
    "txn date": "date",
    "transaction date": "date",
    "value date": "date",
    "posting date": "date",
    # Description
    "description": "description",
    "narration": "description",
    "particulars": "description",
    "details": "description",
    "transaction details": "description",
    "remarks": "description",
    # Amount (single column)
    "amount": "amount",
    "transaction amount": "amount",
    "txn amount": "amount",
    # Debit / Credit (split columns)
    "debit": "debit",
    "withdrawal": "debit",
    "debit amount": "debit",
    "credit": "credit",
    "deposit": "credit",
    "credit amount": "credit",
    # Type
    "type": "type",
    "dr/cr": "type",
    "transaction type": "type",
}

# Date formats to try (most common Indian bank formats first)
_DATE_FORMATS = [
    "%d/%m/%Y",  "%d-%m-%Y",  "%Y-%m-%d",
    "%d/%m/%y",  "%d-%m-%y",  "%m/%d/%Y",
    "%d %b %Y",  "%d-%b-%Y",  "%d %B %Y",
    "%Y/%m/%d",  "%d.%m.%Y",  "%d.%m.%y",
    "%Y-%m-%d %H:%M:%S", "%d/%m/%Y %H:%M:%S", "%d-%m-%Y %H:%M:%S",
    "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%SZ",
]


def parse_csv(file_content: bytes | str) -> list[Transaction]:
    """
    Parse a CSV bank statement into Transaction objects.

    Handles varied header formats across Indian banks by normalizing
    column names through a flexible mapping dictionary.

    Args:
        file_content: Raw CSV bytes or string.

    Returns:
        List of parsed Transaction objects.
    """
    if isinstance(file_content, bytes):
        file_content = file_content.decode("utf-8-sig")  # handle BOM

    reader = csv.DictReader(io.StringIO(file_content))
    if reader.fieldnames is None:
        return []

    # Normalize headers
    col_map: dict[str, str] = {}
    for raw_header in reader.fieldnames:
        canonical = _HEADER_MAP.get(raw_header.strip().lower())
        if canonical:
            col_map[canonical] = raw_header

    if "date" not in col_map or "description" not in col_map:
        raise ValueError(
            f"CSV must contain Date and Description columns. "
            f"Found: {reader.fieldnames}"
        )

    transactions: list[Transaction] = []
    for row in reader:
        try:
            txn = _parse_csv_row(row, col_map)
            if txn:
                transactions.append(txn)
        except Exception:
            continue  # skip malformed rows silently

    return transactions


def _parse_csv_row(row: dict, col_map: dict[str, str]) -> Transaction | None:
    """Parse a single CSV row into a Transaction."""
    # Date
    raw_date = row.get(col_map["date"], "").strip()
    parsed_date = _parse_date(raw_date)
    if parsed_date is None:
        return None

    # Description
    description = row.get(col_map["description"], "").strip()
    if not description:
        return None

    # Amount & type
    amount, txn_type = _parse_amount(row, col_map)
    if amount is None or amount == 0:
        return None

    # Clean merchant name
    merchant_clean = clean_merchant_name(description)

    return Transaction(
        date=parsed_date,
        raw_description=description,
        amount=abs(amount),
        type=txn_type,
        merchant_raw=description,
        merchant_clean=merchant_clean,
    )


def _parse_amount(row: dict, col_map: dict[str, str]) -> tuple[float | None, TransactionType]:
    """
    Extract amount and transaction type from the row.

    Supports three formats:
      1. Single 'amount' column + 'type' column (DR/CR)
      2. Separate 'debit' and 'credit' columns
      3. Single 'amount' column (negative = debit, positive = credit)
    """
    # Format 2: separate debit/credit columns
    if "debit" in col_map or "credit" in col_map:
        debit_val = _to_float(row.get(col_map.get("debit", ""), ""))
        credit_val = _to_float(row.get(col_map.get("credit", ""), ""))
        if debit_val and debit_val > 0:
            return debit_val, TransactionType.DEBIT
        if credit_val and credit_val > 0:
            return credit_val, TransactionType.CREDIT
        return None, TransactionType.DEBIT

    # Format 1 & 3: single amount column
    if "amount" in col_map:
        amount = _to_float(row.get(col_map["amount"], ""))
        if amount is None:
            return None, TransactionType.DEBIT

        # Check explicit type column
        if "type" in col_map:
            type_str = row.get(col_map["type"], "").strip().lower()
            if type_str in ("cr", "credit", "c"):
                return abs(amount), TransactionType.CREDIT
            return abs(amount), TransactionType.DEBIT

        # Infer from sign
        if amount < 0:
            return abs(amount), TransactionType.DEBIT
        return abs(amount), TransactionType.CREDIT

    return None, TransactionType.DEBIT


def _parse_date(date_str: str) -> date | None:
    """Try multiple date formats and return the first that works."""
    if not date_str:
        return None
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(date_str.strip(), fmt).date()
        except ValueError:
            continue
    return None


def _to_float(value: str | None) -> float | None:
    """Convert a string (possibly with commas / currency symbols) to float."""
    if not value:
        return None
    # Remove currency symbols, commas, spaces
    cleaned = re.sub(r"[₹$€,\s]", "", value.strip())
    if not cleaned or cleaned == "-":
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None


# ─── PDF Parsing ──────────────────────────────────────────────────────────────


def parse_pdf(file_content: bytes, password: Optional[str] = None) -> list[Transaction]:
    """
    Extract transactions from a PDF bank statement using a multi-tier parsing pipeline.

    Tiers:
      1. Password Decryption — decrypts password-protected PDFs with user-provided password.
      2. pdfplumber Table Extraction — extracts structured table grids.
      3. Line-by-Line Smart Extraction — parses text lines for dates, amounts, and narrations.
      4. Flex Regex Fallback — fallback line regex for varied layouts.

    Args:
        file_content: Raw PDF bytes.
        password: Optional PDF password string (e.g. DOB, PAN, Account No).

    Returns:
        List of parsed Transaction objects.
    """
    # ── Tier 1: Check Password Protection & Decrypt ──
    try:
        pdf_check = PdfReader(io.BytesIO(file_content))
        if pdf_check.is_encrypted:
            if not password:
                raise ValueError(
                    "This PDF bank statement is password-protected. Please enter your PDF password below (e.g. Date of Birth, PAN, or account digits)."
                )
            decrypt_res = pdf_check.decrypt(password)
            if decrypt_res == 0:
                raise ValueError("Incorrect PDF password. Please check your password and try again.")
            
            # Save decrypted PDF stream in memory
            from pypdf import PdfWriter
            writer = PdfWriter()
            for page in pdf_check.pages:
                writer.add_page(page)
            decrypted_stream = io.BytesIO()
            writer.write(decrypted_stream)
            file_content = decrypted_stream.getvalue()
    except ValueError:
        raise
    except Exception as e:
        if "password" in str(e).lower() or "encrypted" in str(e).lower():
            raise ValueError(
                "This PDF bank statement is password-protected. Please enter your PDF password below."
            )


    # ── Tier 2: Try pdfplumber table extraction ──
    transactions = _parse_pdf_tables_pdfplumber(file_content)
    if transactions:
        return transactions

    # ── Tier 3: Line-by-Line Smart Extraction ──
    full_text = ""
    try:
        import pdfplumber
        with pdfplumber.open(io.BytesIO(file_content)) as pdf:
            for page in pdf.pages:
                full_text += (page.extract_text(layout=False) or "") + "\n"
    except (ImportError, Exception):
        # Fallback to pypdf text extraction
        reader = PdfReader(io.BytesIO(file_content))
        for page in reader.pages:
            full_text += (page.extract_text() or "") + "\n"


    transactions = _parse_pdf_smart_text(full_text)
    if transactions:
        return transactions

    # ── Tier 4: Fallback regex ──
    return _parse_pdf_text_fallback(full_text)


def _parse_pdf_tables_pdfplumber(file_content: bytes) -> list[Transaction]:
    """Extract transactions from PDF using pdfplumber table grids with multi-page header memory."""
    try:
        import pdfplumber
    except ImportError:
        return []

    transactions: list[Transaction] = []
    cached_col_map: dict[str, int] = {}

    try:
        with pdfplumber.open(io.BytesIO(file_content)) as pdf:
            for page in pdf.pages:
                tables = page.extract_tables()
                for table in tables:
                    if not table or len(table) < 1:
                        continue

                    # Search for header row
                    header_idx = -1
                    col_map = {}
                    for idx, row in enumerate(table[:5]):
                        if not row:
                            continue
                        row_str = " ".join(str(c or "").lower() for c in row)
                        if any(kw in row_str for kw in ("date", "txn date", "value date")) and any(kw in row_str for kw in ("narration", "particulars", "description", "details", "withdrawal", "deposit", "amount", "debit", "credit", "balance", "chq")):
                            header_idx = idx
                            # Map columns
                            for c_idx, cell in enumerate(row):
                                cell_lower = str(cell or "").strip().lower()
                                if any(k in cell_lower for k in ("txn date", "transaction date", "value date", "date")):
                                    if "date" not in col_map:
                                        col_map["date"] = c_idx
                                elif any(k in cell_lower for k in ("description", "narration", "particulars", "details", "remarks", "transaction details")):
                                    col_map["description"] = c_idx
                                elif any(k in cell_lower for k in ("withdrawal", "debit", "dr", "dr amount", "withdrawals")):
                                    col_map["debit"] = c_idx
                                elif any(k in cell_lower for k in ("deposit", "credit", "cr", "cr amount", "deposits")):
                                    col_map["credit"] = c_idx
                                elif "amount" in cell_lower and "balance" not in cell_lower:
                                    col_map["amount"] = c_idx
                            break

                    if header_idx != -1 and "date" in col_map:
                        cached_col_map = col_map.copy()
                        start_row = header_idx + 1
                    elif cached_col_map:
                        # Page 2+ continuation without repeated header row!
                        col_map = cached_col_map.copy()
                        start_row = 0
                    else:
                        continue

                    # Parse data rows
                    for row in table[start_row:]:
                        if not row or len(row) <= col_map.get("date", 0):
                            continue

                        raw_date = str(row[col_map["date"]] or "").strip()
                        parsed_date = _parse_date(raw_date)
                        if not parsed_date:
                            continue

                        description = ""
                        if "description" in col_map and len(row) > col_map["description"]:
                            description = str(row[col_map["description"]] or "").strip()
                        if not description:
                            # Fallback: join other non-numeric text columns
                            desc_parts = [str(c or "").strip() for idx, c in enumerate(row) if idx != col_map["date"] and not re.match(r"^[\d,.]+$", str(c or "").strip())]
                            description = " ".join(desc_parts).strip()

                        if not description or len(description) < 2:
                            continue

                        amount = None
                        txn_type = TransactionType.DEBIT

                        if "debit" in col_map or "credit" in col_map:
                            deb = _to_float(str(row[col_map.get("debit", -1)] or "")) if "debit" in col_map and len(row) > col_map["debit"] else None
                            cred = _to_float(str(row[col_map.get("credit", -1)] or "")) if "credit" in col_map and len(row) > col_map["credit"] else None
                            if deb and deb > 0:
                                amount = deb
                                txn_type = TransactionType.DEBIT
                            elif cred and cred > 0:
                                amount = cred
                                txn_type = TransactionType.CREDIT
                        elif "amount" in col_map and len(row) > col_map["amount"]:
                            amount = _to_float(str(row[col_map["amount"]] or ""))
                            txn_type = TransactionType.DEBIT

                        # If amount still not found, search all cells in row for a valid amount float
                        if not amount or amount == 0:
                            for idx, c in enumerate(row):
                                if idx != col_map.get("date"):
                                    cand = _to_float(str(c or ""))
                                    if cand and cand > 0:
                                        amount = cand
                                        break

                        if not amount or amount == 0:
                            continue

                        merchant_clean = clean_merchant_name(description)
                        transactions.append(Transaction(
                            date=parsed_date,
                            raw_description=description,
                            amount=abs(amount),
                            type=txn_type,
                            merchant_raw=description,
                            merchant_clean=merchant_clean,
                        ))
    except Exception:
        pass

    return transactions



def _parse_pdf_smart_text(text: str) -> list[Transaction]:
    """
    Parse text line-by-line looking for dates and amounts anywhere in the line.
    Handles multi-column bank statements where closing balance or ref numbers exist.
    """
    date_regex = re.compile(r"\b(\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{1,2}\s+[A-Za-z]{3}\s+\d{2,4})\b")
    amount_regex = re.compile(r"\b([\d,]+\.\d{2})\b")

    transactions: list[Transaction] = []
    lines = text.split("\n")

    current_date = None
    current_desc = []
    current_amounts = []
    type_hint = None

    for line in lines:
        line_str = line.strip()
        if not line_str:
            continue

        date_match = date_regex.search(line_str)
        if date_match:
            # If we had a previous pending transaction, try to finalize it
            if current_date and current_desc and current_amounts:
                txn = _create_txn_from_tokens(current_date, " ".join(current_desc), current_amounts, type_hint)
                if txn:
                    transactions.append(txn)

            # Start new transaction
            current_date = _parse_date(date_match.group(1))
            # Remove date string from line to process description & amounts
            remainder = line_str[:date_match.start()] + line_str[date_match.end():]
            current_desc = [remainder]
            current_amounts = [float(a.replace(",", "")) for a in amount_regex.findall(remainder)]
            type_hint = "credit" if re.search(r"\b(cr|credit|deposit)\b", remainder, re.I) else None
        elif current_date:
            # Line continuation (multiline description or additional amounts)
            current_desc.append(line_str)
            found_amounts = [float(a.replace(",", "")) for a in amount_regex.findall(line_str)]
            if found_amounts:
                current_amounts.extend(found_amounts)
            if not type_hint and re.search(r"\b(cr|credit|deposit)\b", line_str, re.I):
                type_hint = "credit"

    # Finalize last transaction
    if current_date and current_desc and current_amounts:
        txn = _create_txn_from_tokens(current_date, " ".join(current_desc), current_amounts, type_hint)
        if txn:
            transactions.append(txn)

    return transactions


def _create_txn_from_tokens(txn_date: date, desc_text: str, amounts: list[float], type_hint: str | None) -> Transaction | None:
    """Helper to deduce transaction amount and type from line tokens."""
    if not amounts:
        return None

    # Strip pure numbers/references from description text
    clean_desc = re.sub(r"\b[\d,]+\.\d{2}\b", "", desc_text).strip()
    clean_desc = re.sub(r"\s{2,}", " ", clean_desc)

    if not clean_desc or len(clean_desc) < 2:
        clean_desc = desc_text[:40]

    # Heuristic for amount selection:
    # If 1 amount found -> it's the transaction amount
    # If >= 2 amounts found (e.g. txn amount and balance) -> take the first non-zero amount
    amount = amounts[0]
    txn_type = TransactionType.CREDIT if type_hint == "credit" else TransactionType.DEBIT

    merchant_clean = clean_merchant_name(clean_desc)

    return Transaction(
        date=txn_date,
        raw_description=clean_desc,
        amount=abs(amount),
        type=txn_type,
        merchant_raw=clean_desc,
        merchant_clean=merchant_clean,
    )


def _parse_pdf_text_fallback(text: str) -> list[Transaction]:
    """Fallback regex for raw text."""
    line_pattern = re.compile(
        r"(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})\s+(.+?)\s+([\d,]+\.?\d{0,2})\s*(Dr|Cr|DR|CR)?",
        re.IGNORECASE,
    )

    transactions: list[Transaction] = []
    for match in line_pattern.finditer(text):
        raw_date, description, amount_str, type_str = match.groups()
        parsed_date = _parse_date(raw_date)
        amount = _to_float(amount_str)

        if parsed_date and amount:
            txn_type = TransactionType.CREDIT if type_str and type_str.lower() in ("cr", "credit") else TransactionType.DEBIT
            merchant_clean = clean_merchant_name(description.strip())
            transactions.append(Transaction(
                date=parsed_date,
                raw_description=description.strip(),
                amount=abs(amount),
                type=txn_type,
                merchant_raw=description.strip(),
                merchant_clean=merchant_clean,
            ))

    return transactions
