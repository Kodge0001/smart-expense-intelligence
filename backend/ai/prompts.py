"""
Prompt templates for LLM-based transaction categorization.

Design decisions:
  • We batch 10–20 transactions per API call to minimize cost & latency.
  • The prompt enforces strict JSON output so we can parse deterministically.
  • Category list is exhaustive — the model must pick one.
  • We ask for a cleaned merchant name as a bonus (the LLM often does this
    better than regex for edge cases like "PHONEPE*MERCHANT_XYZ").
"""

from __future__ import annotations

CATEGORY_LIST = [
    "food", "rent", "travel", "shopping", "utilities",
    "entertainment", "subscriptions", "healthcare",
    "transfers", "salary", "other",
]

SYSTEM_PROMPT = """You are a financial transaction categorizer. You will receive a JSON array of bank transactions. For each transaction, you must return a categorization result.

RULES:
1. You MUST respond with ONLY a valid JSON array — no markdown, no explanation.
2. Each element must have exactly these fields:
   - "transaction_id": string (copy from input)
   - "category": one of {categories}
   - "clean_merchant_name": a short, human-readable merchant name
   - "confidence": float between 0.0 and 1.0 (provide a granular, calibrated score, e.g. 0.95 for unambiguous recognizable brands like Netflix or Uber, 0.82 for generic restaurants, 0.65 for ambiguous merchant names).
3. Pick the MOST specific category that applies.
4. For salary/income credits, use "salary".
5. For bank transfers between own accounts, use "transfers".
6. For streaming services, gym memberships, recurring SaaS, use "subscriptions".
7. If truly uncertain, use "other" with confidence around 0.35-0.50.

CATEGORIES: {categories}

Respond with ONLY the JSON array.""".format(categories=", ".join(CATEGORY_LIST))


def build_categorization_prompt(transactions: list[dict]) -> str:
    """
    Build the user-message portion of the categorization prompt.

    Args:
        transactions: List of dicts with keys:
            transaction_id, merchant_name, amount, type

    Returns:
        A JSON string ready to send as the user message.
    """
    import json
    return json.dumps(transactions, indent=2)
