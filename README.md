# 💰 Smart Expense Intelligence System

An AI-powered financial analytics platform that transforms raw bank statements into actionable spending insights. Upload a CSV/PDF statement and get **AI-categorized spending breakdown**, **recurring subscription detection**, and **cash-flow forecasting** — all in an interactive dashboard.

> **Portfolio project** — designed to demonstrate full-stack Python skills, AI integration with cost control, and deliberate architecture decisions (AI vs. deterministic algorithms).

---

## 🏗️ Architecture

```
┌──────────────────────────────────────────────────────┐
│                  Streamlit Frontend                   │
│  Upload • KPI Cards • Charts • Subscriptions • Alerts │
└──────────────────┬───────────────────────────────────┘
                   │  REST API (HTTP)
┌──────────────────▼───────────────────────────────────┐
│                  FastAPI Backend                      │
│                                                      │
│  ┌─────────────┐  ┌──────────────┐  ┌─────────────┐ │
│  │  Ingestion   │  │  AI Layer    │  │  Analytics   │ │
│  │  CSV / PDF   │  │  LLM Batch   │  │  Recurring   │ │
│  │  Parser      │  │  Categorizer │  │  (No AI)     │ │
│  │  Regex Clean │  │  + Cache     │  │  Forecast    │ │
│  └──────┬───────┘  └──────┬───────┘  │  (No AI)     │ │
│         │                 │          └──────┬───────┘ │
│         └────────┬────────┴────────────────┘         │
│                  │                                    │
│         ┌────────▼────────┐                          │
│         │   SQLite DB     │                          │
│         │  Transactions   │                          │
│         │  Category Cache │                          │
│         │  User Overrides │                          │
│         └─────────────────┘                          │
└──────────────────────────────────────────────────────┘
```

---

## 🚀 Quick Start

### 1. Clone & install

```bash
cd expense-intelligence
python -m venv venv
source venv/bin/activate    # macOS/Linux
pip install -r requirements.txt
```

### 2. Configure environment

```bash
cp .env.example .env
# Edit .env and add ONE of:
#   OPENAI_API_KEY=sk-...
#   ANTHROPIC_API_KEY=sk-ant-...
#   GOOGLE_API_KEY=AIza...
#
# Or leave all blank — the app uses a rule-based fallback.
```

### 3. Start the backend

```bash
uvicorn backend.main:app --reload --port 8000
```

### 4. Start the frontend

```bash
streamlit run frontend/app.py
```

### 5. Demo it

1. Click **"Load Sample Data"** in the sidebar (or upload your own CSV/PDF).
2. View the categorized spending breakdown charts.
3. Check the recurring subscriptions table.
4. See the cash-flow warning banner (if a shortfall is predicted).
5. Try overriding a transaction's category — it persists via SQLite.

---

## 📐 Design Decisions & Trade-offs

### Why AI for categorization but NOT for recurring/forecast?

| Concern | Categorization | Recurring Detection | Cash-Flow Forecast |
|---------|---------------|--------------------|--------------------|
| **Problem type** | Open-ended (novel merchants) | Well-defined constraints | Simple projection |
| **Approach** | LLM (batch + cache) | Deterministic algorithm | Rolling average stats |
| **Why this choice?** | Regex can't handle all 10,000+ possible merchant formats | "Same amount, regular interval" = simple math | Linear projection is explainable & auditable |
| **Testability** | Hard to unit-test AI output | ✅ 6 pytest cases | ✅ Deterministic output |
| **Cost** | ~$0.01/batch (cached) | Free | Free |
| **Deterministic?** | No (but cached ≈ yes) | Yes | Yes |

### Cost control strategy

1. **Batch processing**: 15 transactions per LLM call (not 1 call per row)
2. **Merchant-level caching**: Each unique merchant triggers at most ONE API call ever
3. **Rule-based fallback**: Works without any API key for demos
4. **Multi-provider support**: OpenAI, Anthropic, or Google Gemini — use whichever is cheapest

### Why Streamlit over React?

- **Single-language stack** (all Python) → easier to maintain and explain
- **Rapid prototyping** → built-in widgets for file upload, tables, charts
- **Portfolio-appropriate** → shows data science + engineering breadth
- Trade-off: less flexible UI than React, but adequate for a demo/portfolio piece

---

## 🧪 Testing

```bash
# Run the recurring detection unit tests
pytest tests/ -v

# Expected output: 6 tests passed
# - test_clear_monthly_subscription
# - test_irregular_one_off_payments_not_flagged
# - test_edge_case_two_occurrences
# - test_weekly_subscription
# - test_credit_transactions_excluded
# - test_mixed_transactions_only_flags_recurring
```

---

## 📁 Project Structure

```
expense-intelligence/
├── backend/
│   ├── ingestion/
│   │   ├── parser.py          # CSV/PDF → structured transactions
│   │   └── cleaner.py         # Regex merchant name extraction
│   ├── ai/
│   │   ├── categorizer.py     # Batched LLM + cache + fallback
│   │   └── prompts.py         # Strict JSON prompt templates
│   ├── analytics/
│   │   ├── recurring.py       # Deterministic subscription detector
│   │   └── forecast.py        # Statistical cash-flow projection
│   ├── models/
│   │   └── schema.py          # Pydantic data models
│   ├── storage/
│   │   └── db.py              # SQLite persistence
│   └── main.py                # FastAPI REST API
├── frontend/
│   └── app.py                 # Streamlit dashboard
├── data/
│   └── sample_statement.csv   # 61 synthetic Indian bank transactions
├── tests/
│   └── test_recurring.py      # Pytest unit tests (6 cases)
├── .env.example               # Environment variable template
├── requirements.txt           # Python dependencies
└── README.md                  # This file
```

---

## 🛡️ Security Notes

- API keys are loaded from `.env` (never hardcoded)
- `.env` is gitignored
- SQLite database is local-only
- No user data is sent externally except to the configured LLM provider for categorization

---

## 📊 Sample Data

The bundled `sample_statement.csv` contains 61 synthetic Indian bank transactions across June–July 2025, including:

- **4 recurring subscriptions**: Netflix (₹199/mo), Cult Fit gym (₹999/mo), Spotify (₹119/mo), ACT Fibernet (₹799/mo)
- **Regular spending**: Swiggy, Zomato, Uber, Ola, BigBasket, groceries, fuel
- **1 deliberate anomaly**: ₹45,000 Croma electronics purchase (triggers the cash-flow warning)
- **2 salary credits**: ₹85,000/month from "ACME CORP"

---

## 🎯 Interview Defense Points

1. **"Why not use AI for everything?"** — AI is a tool, not a hammer. I use it where it adds unique value (novel merchant categorization) and avoid it where simple algorithms are faster, cheaper, and more testable.

2. **"How do you control AI costs?"** — Batching (15 txns/call), merchant-level caching (each merchant = 1 API call ever), and rule-based fallback for zero-cost demos.

3. **"Why simple statistics over ML for forecasting?"** — A 30-day rolling average is explainable, auditable, and stable. ML models add complexity for marginal gains on a 1–4 week projection window.

4. **"How is this production-ready?"** — SQLite for local persistence, Pydantic validation at every boundary, structured error handling with retries, and comprehensive unit tests for the core algorithm.

---

Built with Python, FastAPI, Streamlit, Plotly, and thoughtful engineering decisions. ✨
