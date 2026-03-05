git remote set-url origin https://SujayPalande:<YOUR_PAT>@github.com/cybaemtech/EDGAR-02Mar-15-50.git
git push -u origin main

# SEC EDGAR Filing Text Extraction API  v2.0

A FastAPI-based REST API that fetches and extracts clean text from SEC EDGAR filings for any public company — with form-type-aware parsing, section-level extraction for 10-K/10-Q, XML parsing for Form 4 insider transactions, full-text search, and a bulk endpoint to pull all key filing types in one call.

## Supported Filing Types

| Form | Description |
|------|-------------|
| `10-K` | Annual Report – audited financials, business overview, risks |
| `10-Q` | Quarterly Report – unaudited Q1–Q3 financials |
| `8-K` | Current Report – major unscheduled corporate events |
| `DEF 14A` | Proxy Statement – shareholder votes, exec compensation |
| `4` | Form 4 – insider transactions (XML-parsed into structured summary) |
| `S-1` | Registration Statement – pre-IPO |

---

## Setup

```bash
pip install -r requirements.txt
uvicorn main:app --reload
```

API available at: `http://localhost:8000`
Interactive docs: `http://localhost:8000/docs`

> **Important:** Update the `USER_AGENT` email in `main.py` to your real contact email before deploying. SEC requires a valid User-Agent.

---

## Endpoints

### `GET /` — API Info
Returns API overview, version, and list of all endpoints.

### `GET /forms` — Supported Forms
Lists supported filing types and available sections for extraction.

---

### `GET /company/{ticker}` — Company Info + Recent Filings
Returns company metadata (CIK, SIC, fiscal year, etc.) and recent filings grouped by type.

```
GET /company/AAPL
GET /company/MSFT
GET /company/BRK-B
```

---

### `GET /filings/{ticker}` — List Filings by Type
Lists filings for a company filtered by form type.

| Param | Required | Description |
|-------|----------|-------------|
| `form_type` | Yes | e.g. `10-K`, `10-Q`, `8-K`, `DEF 14A`, `4`, `S-1` |
| `count` | No (default 10) | Number of results (max 100) |

```
GET /filings/AAPL?form_type=10-K&count=5
GET /filings/TSLA?form_type=8-K&count=20
GET /filings/MSFT?form_type=DEF 14A
```

---

### `GET /filing/text` — Extract Text by Accession Number
Fetches and returns clean text from a specific filing.

| Param | Required | Description |
|-------|----------|-------------|
| `ticker` | Yes | Company ticker |
| `accession_number` | Yes | e.g. `0000320193-23-000106` |
| `form_type` | No | Hint for smarter parsing (e.g. `4` for Form 4 XML) |
| `max_chars` | No (default 100000) | Max characters (up to 1M) |

```
GET /filing/text?ticker=AAPL&accession_number=0000320193-23-000106&form_type=10-K
```

---

### `GET /filing/latest` — Get Latest Filing Text ⭐
Fetches the most recent filing of a given type and returns extracted text. **Most useful endpoint.**

| Param | Required | Description |
|-------|----------|-------------|
| `ticker` | Yes | Company ticker |
| `form_type` | Yes | `10-K`, `10-Q`, `8-K`, `DEF 14A`, `4`, `S-1` |
| `max_chars` | No (default 100000) | Max characters (up to 1M) |

```
# Apple's latest annual report
GET /filing/latest?ticker=AAPL&form_type=10-K

# Tesla's latest current report
GET /filing/latest?ticker=TSLA&form_type=8-K

# Microsoft's latest proxy statement
GET /filing/latest?ticker=MSFT&form_type=DEF 14A

# Insider transactions (Form 4 → structured XML summary)
GET /filing/latest?ticker=AAPL&form_type=4
```

---

### `GET /filing/section` — Section Extraction (10-K / 10-Q) 🆕
Extract a specific section from a 10-K or 10-Q using regex-based Item heading detection.

| Param | Required | Description |
|-------|----------|-------------|
| `ticker` | Yes | Company ticker |
| `form_type` | No (default `10-K`) | `10-K` or `10-Q` |
| `section` | Yes | One of: `business`, `risk_factors`, `properties`, `legal_proceedings`, `md_and_a`, `financials` |
| `accession_number` | No | Specific filing (omit for latest) |
| `max_chars` | No (default 100000) | Max characters |

```
# Apple's risk factors from latest 10-K
GET /filing/section?ticker=AAPL&section=risk_factors

# Microsoft's MD&A from latest 10-Q
GET /filing/section?ticker=MSFT&form_type=10-Q&section=md_and_a
```

---

### `GET /filing/bulk-latest` — Bulk Latest Filings 🆕
Fetch the latest filing of **every key form type** in one call. Great for a full disclosure snapshot.

| Param | Required | Description |
|-------|----------|-------------|
| `ticker` | Yes | Company ticker |
| `form_types` | No | Comma-separated (default: `10-K,10-Q,8-K,DEF 14A,4,S-1`) |
| `max_chars_each` | No (default 20000) | Max chars per filing |

```
GET /filing/bulk-latest?ticker=AAPL
GET /filing/bulk-latest?ticker=MSFT&form_types=10-K,8-K&max_chars_each=50000
```

---

### `GET /search` — Full-Text Search 🆕
Search across EDGAR filings using the SEC EFTS (full-text search) engine.

| Param | Required | Description |
|-------|----------|-------------|
| `q` | Yes | Search query text |
| `form_type` | No | Filter by form type |
| `ticker` | No | Filter by company |
| `date_from` | No | Start date `YYYY-MM-DD` |
| `date_to` | No | End date `YYYY-MM-DD` |
| `count` | No (default 10) | Number of results (max 50) |

```
GET /search?q=acquisition&form_type=8-K&ticker=MSFT
GET /search?q=cybersecurity+risk&form_type=10-K&date_from=2024-01-01
```

---

## Key Improvements in v2.0

| Feature | v1 | v2 |
|---------|----|----|
| Form 4 XML parsing | Raw HTML strip | Structured issuer/owner/transaction summary |
| Primary doc detection | HTML index scraping | JSON index + largest-file heuristic |
| Rate limiting | None | Token-bucket 9 req/s (SEC limit: 10) |
| Caching | None | In-memory TTL cache for CIK map + submissions |
| Connection pooling | New client per request | Shared `httpx.AsyncClient` |
| XBRL inline tags | Removed with text | Unwrapped (preserving text) |
| Section extraction | Not available | 6 sections from 10-K/10-Q |
| Bulk endpoint | Not available | All form types in one call |
| Full-text search | Not available | EDGAR EFTS integration |
| Max chars | 500K | 1M |

---

## SEC Filing Types — What They Contain

- **10-K (Annual Report):** Comprehensive business overview, audited financial statements, risk factors, MD&A, and legal proceedings.
- **10-Q (Quarterly Report):** Unaudited financial statements and updates for the first three quarters.
- **8-K (Current Report):** Major unscheduled events — acquisitions, bankruptcy, CEO changes, material agreements.
- **DEF 14A (Proxy Statement):** Information for shareholder votes on board elections, executive compensation.
- **Form 4 (Insider Transactions):** Stock purchases/sales by directors, officers, and 10%+ owners.
- **S-1 (Registration Statement):** Pre-IPO filing with business model, financials, use of proceeds.

---

## How to Find SEC Filings

- **EDGAR Database:** Free at [sec.gov/edgar](https://www.sec.gov/edgar/) — the primary public source.
- **Investor Relations:** Most public companies link SEC filings from their IR pages.
- **This API:** Programmatic access to all of the above.

---

## Architecture

```
Ticker → CIK Resolution (company_tickers.json, cached)
           ↓
EDGAR Submissions API (data.sec.gov/submissions/CIK{cik}.json, cached)
           ↓
Filing Index JSON (Archives/edgar/data/{cik}/{acc}/index.json)
           ↓
Primary Document Detection (largest .htm, or .xml for Form 4)
           ↓
Form-Type-Aware Parsing:
  ├─ HTML/XBRL → BeautifulSoup → clean text
  ├─ Form 4 XML → ElementTree → structured summary
  └─ Section extraction (10-K/10-Q) → regex Item anchors
```

---

## Notes

- **Rate Limiting:** Built-in async token-bucket limiter (9 req/s) keeps you within SEC's 10/s fair-access policy.
- **User-Agent:** Update `USER_AGENT` in `main.py` to your email — SEC requires it.
- **Large Filings:** 10-K and S-1 can exceed 500K chars. Use `max_chars` to control response size.
- **Caching:** CIK map and submission metadata are cached for 10 minutes to reduce SEC load.
