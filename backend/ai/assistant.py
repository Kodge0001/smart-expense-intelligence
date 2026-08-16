"""
Smart Financial Chatbot & Natural Language Query Assistant.

Answers user queries regarding transactions, person transfers (e.g. Veeresh),
category spendings (Food, Travel, Subscriptions), highest expenses, and monthly totals.
Uses configured LLM (OpenAI, Anthropic, Gemini) or intelligent rule-based aggregation fallback.
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Optional

from backend.ai.categorizer import _call_llm, _get_llm_provider
from backend.models.schema import Transaction, TransactionType


def answer_financial_query(query: str, transactions: list[Transaction]) -> str:
    """
    Answers a natural language query about the user's transactions.
    """
    if not query or not query.strip():
        return "Please ask a question about your bank statement or transactions."

    if not transactions:
        return "No transactions are currently loaded. Please upload a bank statement or load sample data first."

    # Try LLM first if available
    provider = _get_llm_provider()
    if provider:
        response = _answer_with_llm(query, transactions)
        if response:
            return response

    # Fallback to local intelligent query engine
    return _answer_deterministic(query, transactions)


def _answer_with_llm(query: str, transactions: list[Transaction]) -> Optional[str]:
    """Use configured LLM with compact transaction context to generate an accurate answer."""
    # Build lightweight transaction summary (up to 75 txns to respect context limits)
    sorted_txns = sorted(transactions, key=lambda t: t.date, reverse=True)[:75]
    summary_lines = []
    for t in sorted_txns:
        sign = "-" if t.type == TransactionType.DEBIT else "+"
        summary_lines.append(
            f"{t.date.isoformat()} | {sign}₹{t.amount:,.2f} | {t.merchant_clean} | {t.category.value} | {t.raw_description[:45]}"
        )
    context_str = "\n".join(summary_lines)

    total_spent = sum(t.amount for t in transactions if t.type == TransactionType.DEBIT)
    total_received = sum(t.amount for t in transactions if t.type == TransactionType.CREDIT)

    system_prompt = f"""You are a personal financial AI assistant analyzing the user's bank statement.
Total Outflow: ₹{total_spent:,.2f} | Total Inflow: ₹{total_received:,.2f} | Total Transactions: {len(transactions)}

Transaction Records (Format: Date | Amount | Clean Name | Category | Narration):
{context_str}

Instructions:
1. Answer the user's question directly, accurately, and concisely using the provided transaction data.
2. Include specific dates, exact amounts in INR (₹), and person/merchant names where applicable.
3. If asking about a specific person (e.g. Veeresh, Rahul) or merchant (e.g. Swiggy), calculate the exact sum of transactions paid/received with them.
4. Keep the tone helpful, professional, and crisp."""

    return _call_llm(system_prompt, query)


def _answer_deterministic(query: str, transactions: list[Transaction]) -> str:
    """Deterministic natural language parser for calculations without LLM API key."""
    q_lower = query.lower()

    # 1. Total spent or total inflow
    if any(k in q_lower for k in ("total spend", "total expense", "how much did i spend in total", "overall spend")):
        total_debits = sum(t.amount for t in transactions if t.type == TransactionType.DEBIT)
        return f"📊 Your total outflow across all recorded transactions is **₹{total_debits:,.2f}** across {len([t for t in transactions if t.type == TransactionType.DEBIT])} debit transactions."

    if any(k in q_lower for k in ("total income", "total credit", "how much did i earn", "total received")):
        total_credits = sum(t.amount for t in transactions if t.type == TransactionType.CREDIT)
        return f"💰 Your total inflow/credit across all recorded transactions is **₹{total_credits:,.2f}**."

    # 2. Highest / Largest transaction
    if any(k in q_lower for k in ("highest", "largest", "biggest", "max transaction", "most expensive")):
        debits = [t for t in transactions if t.type == TransactionType.DEBIT]
        if debits:
            max_txn = max(debits, key=lambda t: t.amount)
            return f"🏆 Your highest transaction was **₹{max_txn.amount:,.2f}** paid to **{max_txn.merchant_clean}** on **{max_txn.date.strftime('%d %b %Y')}** (Category: {max_txn.category.value.title()})."

    # 3. Specific item search in narrations or merchants (e.g. "tea", "chai", "coffee", "petrol", "flight", "swiggy", "netflix")
    words = re.findall(r"\b[A-Za-z0-9]{3,}\b", q_lower)
    stop_words = {"how", "much", "paid", "sent", "spend", "spent", "what", "where", "when", "total", "give", "tell", "show", "many", "time", "date", "with", "from", "about"}
    search_terms = [w for w in words if w not in stop_words]

    for term in search_terms:
        # Check matching transactions by merchant_clean or raw_description
        matching_txns = [
            t for t in transactions
            if term in t.merchant_clean.lower() or term in t.raw_description.lower()
        ]
        if matching_txns:
            total_paid = sum(t.amount for t in matching_txns if t.type == TransactionType.DEBIT)
            total_rec = sum(t.amount for t in matching_txns if t.type == TransactionType.CREDIT)
            
            details = []
            for t in sorted(matching_txns, key=lambda x: x.date, reverse=True)[:5]:
                t_type = "Debit" if t.type == TransactionType.DEBIT else "Credit"
                details.append(f"• **{t.date.strftime('%d %b %Y')}**: {t.merchant_clean} ({t_type} ₹{t.amount:,.2f})")
            
            detail_str = "\n".join(details)
            term_title = term.title()
            resp = f"🔍 Found **{len(matching_txns)}** transaction(s) matching **'{term_title}'**:\n\n"
            if total_paid > 0:
                resp += f"• **Total Paid / Spent:** ₹{total_paid:,.2f}\n"
            if total_rec > 0:
                resp += f"• **Total Received:** ₹{total_rec:,.2f}\n"
            resp += f"\n**Matching Transactions:**\n{detail_str}"
            return resp

    # 4. Category-specific queries (Food, Travel, Subscriptions, Shopping, etc.)
    categories = ["food", "travel", "subscriptions", "shopping", "utilities", "entertainment", "healthcare", "rent", "transfers"]
    for cat in categories:
        if cat in q_lower:
            cat_txns = [t for t in transactions if t.category.value.lower() == cat and t.type == TransactionType.DEBIT]
            cat_total = sum(t.amount for t in cat_txns)
            top_m = {}
            for t in cat_txns:
                top_m[t.merchant_clean] = top_m.get(t.merchant_clean, 0.0) + t.amount
            sorted_top = sorted(top_m.items(), key=lambda x: x[1], reverse=True)[:3]
            top_str = ", ".join([f"{name} (₹{amt:,.0f})" for name, amt in sorted_top]) if sorted_top else "None"
            return f"📂 **{cat.title()} Spending:** Total spent is **₹{cat_total:,.2f}** across {len(cat_txns)} transactions.\n\n• **Top places:** {top_str}"

    # General fallback
    total_debits = sum(t.amount for t in transactions if t.type == TransactionType.DEBIT)
    return f"I searched your {len(transactions)} transactions (Total Outflow: ₹{total_debits:,.2f}). You can ask me questions like:\n- *'How much did I pay to Veeresh?'*\n- *'How much did I spend on Tea or Coffee?'*\n- *'What is my total Swiggy spend?'*\n- *'What was my highest expense?'*"
