"""
SEC EDGAR Filing Text Extraction API  v2.0
Pulls text from 10-K, 10-Q, 8-K, DEF 14A, Form 4, S-1 filings for any public company.

Enhancements over v1:
  - Form-type-aware document detection (primary doc from submissions JSON)
  - XML parsing for Form 4 insider-transaction filings
  - Section-level extraction for 10-K / 10-Q (e.g. Risk Factors, MD&A)
  - Async rate-limiter (≤10 req/s) to comply with SEC fair-access policy
  - Bulk endpoint: fetch latest filing of every key type in one call
  - In-memory LRU cache for CIK lookups and submission metadata
  - EDGAR full-text search endpoint (EFTS)
"""

from pathlib import Path
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import httpx
import asyncio
import re
import time
import json
import xml.etree.ElementTree as ET
from typing import Optional, List, Dict, Any
from functools import lru_cache
from bs4 import BeautifulSoup

# ═══════════════════════════════════════════════════════════════
# APP SETUP
# ═══════════════════════════════════════════════════════════════

app = FastAPI(
    title="SEC EDGAR Filing API",
    description=(
        "Extract text from SEC filings (10-K, 10-Q, 8-K, DEF 14A, Form 4, S-1) "
        "for any publicly-listed company.  Data sourced from SEC EDGAR."
    ),
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Configuration ─────────────────────────────────────────────
USER_AGENT = "sujay.palande@cybaemtech.com"   # ← replace with your real email before deploying

EDGAR_BASE = "https://data.sec.gov"
EFTS_BASE = "https://efts.sec.gov/LATEST"
SEC_BASE = "https://www.sec.gov"

SUPPORTED_FORMS: Dict[str, str] = {
    "10-K":    "Annual Report – comprehensive overview, audited financials, and risk factors",
    "10-Q":    "Quarterly Report – unaudited financials for Q1-Q3",
    "8-K":     "Current Report – major unscheduled corporate events",
    "DEF 14A": "Proxy Statement – shareholder vote info (board elections, exec compensation)",
    "4":       "Form 4 – insider transactions (directors, officers, beneficial owners)",
    "S-1":     "Registration Statement – filed prior to an IPO",
}

# 10-K / 10-Q sections we know how to slice out
SECTION_PATTERNS_10K: Dict[str, list] = {
    "business":           [r"item\s*1[.\s]", r"item\s*1a[.\s]"],
    "risk_factors":       [r"item\s*1a[.\s]", r"item\s*1b[.\s]"],
    "properties":         [r"item\s*2[.\s]", r"item\s*3[.\s]"],
    "legal_proceedings":  [r"item\s*3[.\s]", r"item\s*4[.\s]"],
    "md_and_a":           [r"item\s*7[.\s]", r"item\s*7a[.\s]"],
    "financials":         [r"item\s*8[.\s]", r"item\s*9[.\s]"],
}


# ═══════════════════════════════════════════════════════════════
# RATE LIMITER  (token-bucket, 10 req / second for SEC)
# ═══════════════════════════════════════════════════════════════

class _RateLimiter:
    """Simple async token-bucket limiter using asyncio.sleep (event-loop safe)."""
    def __init__(self, max_per_sec: int = 9):
        self._min_interval = 1.0 / max_per_sec
        self._last_time = 0.0
        self._lock: Optional[asyncio.Lock] = None  # lazy-init to avoid event-loop binding at import

    async def acquire(self):
        if self._lock is None:
            self._lock = asyncio.Lock()
        try:
            async with self._lock:
                now = time.monotonic()
                elapsed = now - self._last_time
                if elapsed < self._min_interval:
                    await asyncio.sleep(self._min_interval - elapsed)
                self._last_time = time.monotonic()
        except RuntimeError:
            # Event loop changed — recreate lock
            self._lock = asyncio.Lock()
            async with self._lock:
                now = time.monotonic()
                elapsed = now - self._last_time
                if elapsed < self._min_interval:
                    await asyncio.sleep(self._min_interval - elapsed)
                self._last_time = time.monotonic()

_limiter = _RateLimiter(max_per_sec=9)   # stay safely under 10/s


# ═══════════════════════════════════════════════════════════════
# SHARED HTTP CLIENT  (connection-pooled, rate-limited)
# ═══════════════════════════════════════════════════════════════

_http_client: Optional[httpx.AsyncClient] = None

async def _client() -> httpx.AsyncClient:
    global _http_client
    if _http_client is not None:
        try:
            if _http_client.is_closed:
                _http_client = None
        except RuntimeError:
            _http_client = None
    if _http_client is None:
        _http_client = httpx.AsyncClient(
            headers={"User-Agent": USER_AGENT, "Accept-Encoding": "gzip, deflate"},
            follow_redirects=True,
            timeout=30,
        )
    return _http_client

@app.on_event("shutdown")
async def _shutdown():
    if _http_client and not _http_client.is_closed:
        await _http_client.aclose()


async def _sec_get(url: str, **kwargs) -> httpx.Response:
    """GET with rate-limiting and event-loop resilience."""
    await _limiter.acquire()
    try:
        client = await _client()
        return await client.get(url, **kwargs)
    except RuntimeError:
        # Event loop changed — recreate client
        global _http_client
        if _http_client and not _http_client.is_closed:
            try:
                await _http_client.aclose()
            except Exception:
                pass
        _http_client = httpx.AsyncClient(
            headers={"User-Agent": USER_AGENT, "Accept-Encoding": "gzip, deflate"},
            follow_redirects=True,
            timeout=30,
        )
        return await _http_client.get(url, **kwargs)


# ═══════════════════════════════════════════════════════════════
# CACHES
# ═══════════════════════════════════════════════════════════════

_ticker_map: Optional[Dict[str, str]] = None          # ticker → zero-padded CIK
_ticker_map_ts: float = 0
_submissions_cache: Dict[str, tuple] = {}              # cik → (timestamp, data)
_CACHE_TTL = 600  # seconds


# ═══════════════════════════════════════════════════════════════
# HELPER: Ticker → CIK
# ═══════════════════════════════════════════════════════════════

async def _load_ticker_map() -> Dict[str, str]:
    global _ticker_map, _ticker_map_ts
    if _ticker_map and (time.time() - _ticker_map_ts) < _CACHE_TTL:
        return _ticker_map
    url = f"{SEC_BASE}/files/company_tickers.json"
    r = await _sec_get(url)
    r.raise_for_status()
    data = r.json()
    _ticker_map = {
        entry["ticker"].upper(): str(entry["cik_str"]).zfill(10)
        for entry in data.values()
    }
    _ticker_map_ts = time.time()
    return _ticker_map


async def get_cik_from_ticker(ticker: str) -> str:
    tmap = await _load_ticker_map()
    cik = tmap.get(ticker.upper())
    if not cik:
        raise HTTPException(status_code=404, detail=f"Ticker '{ticker}' not found in SEC database.")
    return cik


# ═══════════════════════════════════════════════════════════════
# HELPER: Submissions (with cache)
# ═══════════════════════════════════════════════════════════════

async def get_company_submissions(cik_padded: str) -> dict:
    now = time.time()
    if cik_padded in _submissions_cache:
        ts, cached = _submissions_cache[cik_padded]
        if now - ts < _CACHE_TTL:
            return cached

    url = f"{EDGAR_BASE}/submissions/CIK{cik_padded}.json"
    r = await _sec_get(url)
    if r.status_code == 404:
        raise HTTPException(status_code=404, detail=f"CIK {cik_padded} not found in EDGAR.")
    r.raise_for_status()
    data = r.json()
    _submissions_cache[cik_padded] = (now, data)
    return data


# ═══════════════════════════════════════════════════════════════
# HELPER: HTML / XML → Clean text
# ═══════════════════════════════════════════════════════════════

def clean_html_to_text(html: str) -> str:
    """Strip HTML/XBRL tags and return readable text.
    Handles iXBRL filings by removing metadata elements and hidden context divs.
    """
    soup = BeautifulSoup(html, "html.parser")
    # Remove non-content elements
    for tag in soup(["script", "style", "head", "meta", "link"]):
        tag.decompose()
    # Remove iXBRL structural/metadata elements (header, hidden, resources, references)
    for el in soup.find_all(re.compile(r"^ix:(header|hidden|resources|references)", re.I)):
        el.decompose()
    # Remove hidden divs (XBRL context data rendered as display:none)
    for div in soup.find_all("div", style=re.compile(r"display\s*:\s*none", re.I)):
        div.decompose()
    # Remove hidden spans too
    for span in soup.find_all("span", style=re.compile(r"display\s*:\s*none", re.I)):
        span.decompose()
    # Unwrap remaining iXBRL inline tags (keep their text content)
    for ixbrl in soup.find_all(re.compile(r"^(ix:|xbrli:)", re.I)):
        ixbrl.unwrap()
    text = soup.get_text(separator="\n")
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]{2,}", " ", text)
    return text.strip()


def parse_form4_xml(xml_text: str) -> str:
    """Parse Form 4 XML into a human-readable summary."""
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        # Fallback: strip tags and return raw text
        return clean_html_to_text(xml_text)

    ns = ""
    # Some Form 4 XMLs use a default namespace
    m = re.match(r"\{(.+?)\}", root.tag)
    if m:
        ns = m.group(1)

    def _find(el, path):
        if ns:
            path = "/".join(f"{{{ns}}}{p}" for p in path.split("/"))
        found = el.find(path)
        return found.text.strip() if found is not None and found.text else ""

    lines: list = []

    # Issuer
    issuer = root.find(f"{{{ns}}}issuer" if ns else "issuer")
    if issuer is not None:
        lines.append("═══ ISSUER ═══")
        lines.append(f"  Name:   {_find(issuer, 'issuerName')}")
        lines.append(f"  Ticker: {_find(issuer, 'issuerTradingSymbol')}")
        lines.append(f"  CIK:    {_find(issuer, 'issuerCik')}")

    # Reporting owner(s)
    for owner in root.findall(f"{{{ns}}}reportingOwner" if ns else "reportingOwner"):
        lines.append("\n═══ REPORTING OWNER ═══")
        oid = owner.find(f"{{{ns}}}reportingOwnerId" if ns else "reportingOwnerId")
        if oid is not None:
            lines.append(f"  Name: {_find(oid, 'rptOwnerName')}")
            lines.append(f"  CIK:  {_find(oid, 'rptOwnerCik')}")
        rel = owner.find(f"{{{ns}}}reportingOwnerRelationship" if ns else "reportingOwnerRelationship")
        if rel is not None:
            roles = []
            if _find(rel, "isDirector") == "1": roles.append("Director")
            if _find(rel, "isOfficer") == "1": roles.append(f"Officer ({_find(rel, 'officerTitle')})")
            if _find(rel, "isTenPercentOwner") == "1": roles.append("10%+ Owner")
            lines.append(f"  Roles: {', '.join(roles) if roles else 'N/A'}")

    # Non-derivative transactions
    nd = root.find(f"{{{ns}}}nonDerivativeTable" if ns else "nonDerivativeTable")
    if nd is not None:
        lines.append("\n═══ NON-DERIVATIVE TRANSACTIONS ═══")
        for txn in nd.findall(f"{{{ns}}}nonDerivativeTransaction" if ns else "nonDerivativeTransaction"):
            sec_title = _find(txn, "securityTitle/value")
            date = _find(txn, "transactionDate/value")
            coding = txn.find(f"{{{ns}}}transactionCoding" if ns else "transactionCoding")
            code = _find(coding, "transactionCode") if coding is not None else ""
            amounts = txn.find(f"{{{ns}}}transactionAmounts" if ns else "transactionAmounts")
            shares = _find(amounts, "transactionShares/value") if amounts is not None else ""
            price = _find(amounts, "transactionPricePerShare/value") if amounts is not None else ""
            acq_disp = _find(amounts, "transactionAcquiredDisposedCode/value") if amounts is not None else ""
            post = txn.find(f"{{{ns}}}postTransactionAmounts" if ns else "postTransactionAmounts")
            held = _find(post, "sharesOwnedFollowingTransaction/value") if post is not None else ""
            lines.append(f"  {date} | {sec_title} | Code={code} | {acq_disp} {shares} shares @ ${price} | Post-txn held: {held}")

    # Derivative transactions
    dt = root.find(f"{{{ns}}}derivativeTable" if ns else "derivativeTable")
    if dt is not None:
        lines.append("\n═══ DERIVATIVE TRANSACTIONS ═══")
        for txn in dt.findall(f"{{{ns}}}derivativeTransaction" if ns else "derivativeTransaction"):
            sec_title = _find(txn, "securityTitle/value")
            date = _find(txn, "transactionDate/value")
            lines.append(f"  {date} | {sec_title}")

    return "\n".join(lines) if lines else clean_html_to_text(xml_text)


# ═══════════════════════════════════════════════════════════════
# HELPER: Resolve primary document URL for a filing
# ═══════════════════════════════════════════════════════════════

async def _resolve_primary_document(
    cik: str, accession_number: str, form_type: str = "", primary_doc_hint: str = ""
) -> tuple:
    """
    Resolve the primary document URL for a filing.
    Uses primary_doc_hint (from submissions API) when available, falls back to index.json.
    Returns (doc_url, doc_filename).
    """
    acc_clean = accession_number.replace("-", "")
    base_path = f"{SEC_BASE}/Archives/edgar/data/{int(cik)}/{acc_clean}"

    # If we already know the primary document name from submissions API, use it directly
    if primary_doc_hint:
        form_upper = form_type.strip().upper()
        # For Form 4, prefer .xml if the hint isn't already XML
        if form_upper == "4" and not primary_doc_hint.endswith(".xml"):
            # Still try index.json to find the XML, but fall through to hint if not found
            pass
        else:
            return f"{base_path}/{primary_doc_hint}", primary_doc_hint

    # Fall back to scraping the filing index HTML
    index_url = f"{base_path}/{accession_number}-index.htm"

    # First, try the submissions-level primary document info
    # (already available in submissions JSON, passed by callers when possible)

    # Try the index JSON from EDGAR Archives
    try:
        r = await _sec_get(f"{base_path}/index.json")
        if r.status_code == 200:
            idx = r.json()
            items = idx.get("directory", {}).get("item", [])
            form_upper = form_type.strip().upper()

            # For Form 4 prefer the XML document
            if form_upper == "4":
                for item in items:
                    name = item.get("name", "")
                    if name.endswith(".xml") and "primary_doc" not in name.lower():
                        return f"{base_path}/{name}", name

            # For other forms, pick the primary HTML/HTM document (largest .htm file usually)
            htm_candidates = []
            for item in items:
                name = item.get("name", "")
                ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
                if ext in ("htm", "html") and "index" not in name.lower() and "R" not in name[:2]:
                    size = int(item.get("size", 0))
                    htm_candidates.append((size, name))
            if htm_candidates:
                # Pick the largest (usually the full document)
                htm_candidates.sort(reverse=True)
                best = htm_candidates[0][1]
                return f"{base_path}/{best}", best

            # Fallback: any .txt that's not an index
            for item in items:
                name = item.get("name", "")
                if name.endswith(".txt") and "index" not in name.lower():
                    return f"{base_path}/{name}", name

    except Exception:
        pass

    # Last resort: scrape the HTML index
    try:
        r = await _sec_get(index_url)
        if r.status_code == 200:
            soup = BeautifulSoup(r.text, "html.parser")
            for row in soup.find_all("tr"):
                cells = row.find_all("td")
                if len(cells) >= 3:
                    link = cells[2].find("a")
                    if link and link.get("href"):
                        href = link["href"]
                        if href.endswith((".htm", ".html", ".txt", ".xml")) and "index" not in href.lower():
                            url = href if href.startswith("http") else f"{SEC_BASE}{href}"
                            return url, href.split("/")[-1]
    except Exception:
        pass

    # Ultimate fallback
    return f"{base_path}/{accession_number}.txt", f"{accession_number}.txt"


# ═══════════════════════════════════════════════════════════════
# HELPER: Fetch & parse filing text (form-type-aware)
# ═══════════════════════════════════════════════════════════════

async def fetch_filing_text(
    cik: str, accession_number: str, form_type: str = "", primary_doc_hint: str = ""
) -> str:
    doc_url, doc_name = await _resolve_primary_document(
        cik, accession_number, form_type, primary_doc_hint
    )

    r = await _sec_get(doc_url, timeout=60)
    if r.status_code != 200:
        raise HTTPException(status_code=502, detail=f"Could not fetch document at {doc_url}")

    content = r.text

    # For Form 4 XML → structured summary
    if form_type.strip().upper() == "4" and (doc_name.endswith(".xml") or content.lstrip().startswith("<?xml")):
        return parse_form4_xml(content)

    text = clean_html_to_text(content)

    # Detect iXBRL viewer wrapper (returns ~61 chars: "Please enable JavaScript...")
    if len(text) < 200 and "enable javascript" in text.lower():
        # Fallback: try the full-submission text file
        acc_clean = accession_number.replace("-", "")
        fallback_url = f"{SEC_BASE}/Archives/edgar/data/{int(cik)}/{acc_clean}/{accession_number}.txt"
        try:
            r2 = await _sec_get(fallback_url, timeout=60)
            if r2.status_code == 200 and len(r2.text) > 200:
                return clean_html_to_text(r2.text)
        except Exception:
            pass

    return text


# ═══════════════════════════════════════════════════════════════
# HELPER: Section extraction from 10-K / 10-Q full text
# ═══════════════════════════════════════════════════════════════

def extract_section(full_text: str, section: str) -> Optional[str]:
    """
    Attempt to carve out a named section from a 10-K or 10-Q full text.
    Uses regex anchors based on standard Item headings.
    Returns None if the section cannot be reliably located.
    """
    patterns = SECTION_PATTERNS_10K.get(section.lower())
    if not patterns or len(patterns) < 2:
        return None

    start_pat, end_pat = patterns
    # Search for the last occurrence of the start anchor (often the table-of-contents
    # also contains the heading, so we want the actual section body later in the doc)
    starts = list(re.finditer(start_pat, full_text, re.IGNORECASE))
    if not starts:
        return None
    start_match = starts[-1]

    ends = list(re.finditer(end_pat, full_text[start_match.end():], re.IGNORECASE))
    if ends:
        return full_text[start_match.start(): start_match.end() + ends[0].start()].strip()
    # If no end anchor, return up to 50k chars from start
    return full_text[start_match.start(): start_match.start() + 50000].strip()


# ═══════════════════════════════════════════════════════════════
# HELPER: Common filing list builder
# ═══════════════════════════════════════════════════════════════

def _build_filing_list(recent: dict, cik: str, form_type: str, count: int) -> list:
    forms = recent.get("form", [])
    dates = recent.get("filingDate", [])
    accessions = recent.get("accessionNumber", [])
    primary_docs = recent.get("primaryDocument", [])
    descriptions = recent.get("primaryDocDescription", [])

    form_type_upper = form_type.strip().upper()
    results = []
    for i, (form, date, acc) in enumerate(zip(forms, dates, accessions)):
        if form.strip().upper() == form_type_upper:
            results.append({
                "form_type": form,
                "filing_date": date,
                "accession_number": acc,
                "primary_document": primary_docs[i] if i < len(primary_docs) else None,
                "description": descriptions[i] if i < len(descriptions) else None,
                "filing_url": f"{SEC_BASE}/Archives/edgar/data/{int(cik)}/{acc.replace('-','')}/{acc}-index.htm",
            })
            if len(results) >= count:
                break
    return results


# ═══════════════════════════════════════════════════════════════
# ENDPOINTS
# ═══════════════════════════════════════════════════════════════

@app.get("/", summary="API Info", tags=["General"])
def root():
    return {
        "api": "SEC EDGAR Filing Text Extraction API",
        "version": "2.0.0",
        "supported_form_types": SUPPORTED_FORMS,
        "endpoints": {
            "GET /company/{ticker}": "Company info + recent filings grouped by type",
            "GET /filings/{ticker}": "List filings filtered by form type",
            "GET /filing/text": "Extract text from a specific filing (by accession number)",
            "GET /filing/latest": "Extract text from the most recent filing of a given type",
            "GET /filing/section": "Extract a specific section from a 10-K or 10-Q",
            "GET /filing/bulk-latest": "Latest filing text for ALL key form types in one call",
            "GET /search": "Full-text search across EDGAR filings",
            "GET /forms": "List supported form types with descriptions",
        },
    }


@app.get("/forms", summary="List supported filing types", tags=["General"])
def list_forms():
    return {
        "supported_forms": SUPPORTED_FORMS,
        "section_extraction_available_for": ["10-K", "10-Q"],
        "extractable_sections": list(SECTION_PATTERNS_10K.keys()),
    }


# ───────────────────────────────────────────── Company Info
@app.get("/company/{ticker}", summary="Company info + recent filings", tags=["Company"])
async def get_company_info(ticker: str):
    """Resolve a ticker to its CIK and return company metadata with filings grouped by type."""
    cik = await get_cik_from_ticker(ticker)
    data = await get_company_submissions(cik)

    recent = data.get("filings", {}).get("recent", {})
    forms = recent.get("form", [])
    dates = recent.get("filingDate", [])
    accessions = recent.get("accessionNumber", [])

    filings_by_type: Dict[str, list] = {}
    for form, date, acc in zip(forms, dates, accessions):
        fk = form.strip()
        filings_by_type.setdefault(fk, [])
        if len(filings_by_type[fk]) < 5:
            filings_by_type[fk].append({"date": date, "accession_number": acc})

    return {
        "ticker": ticker.upper(),
        "cik": cik,
        "company_name": data.get("name"),
        "sic": data.get("sic"),
        "sic_description": data.get("sicDescription"),
        "state_of_incorporation": data.get("stateOfIncorporation"),
        "fiscal_year_end": data.get("fiscalYearEnd"),
        "exchanges": data.get("exchanges"),
        "entity_type": data.get("entityType"),
        "ein": data.get("ein"),
        "website": (data.get("website") or [""])[0] if isinstance(data.get("website"), list) else data.get("website"),
        "investor_relations": f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK={cik}&type=&dateb=&owner=include&count=40",
        "edgar_page": f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK={cik}&type=&dateb=&owner=include&count=40&search_text=&action=getcompany",
        "recent_filings_by_type": filings_by_type,
    }


# ───────────────────────────────────────────── List Filings
@app.get("/filings/{ticker}", summary="List filings by form type", tags=["Filings"])
async def list_filings(
    ticker: str,
    form_type: str = Query(..., description="e.g. 10-K, 10-Q, 8-K, DEF 14A, 4, S-1"),
    count: int = Query(10, ge=1, le=100, description="Number of filings to return"),
):
    """List filings for a company filtered by form type."""
    cik = await get_cik_from_ticker(ticker)
    data = await get_company_submissions(cik)
    recent = data.get("filings", {}).get("recent", {})

    results = _build_filing_list(recent, cik, form_type, count)
    if not results:
        raise HTTPException(status_code=404, detail=f"No {form_type} filings found for {ticker.upper()}.")

    return {
        "ticker": ticker.upper(),
        "cik": cik,
        "company_name": data.get("name"),
        "form_type": form_type,
        "count": len(results),
        "filings": results,
    }


# ───────────────────────────────────────────── Filing Text (by accession)
@app.get("/filing/text", summary="Extract text from a specific filing", tags=["Filing Text"])
async def get_filing_text(
    ticker: str = Query(..., description="Company ticker, e.g. AAPL"),
    accession_number: str = Query(..., description="Accession number, e.g. 0000320193-23-000106"),
    form_type: str = Query("", description="Optional form type hint for smarter parsing (e.g. 4 for Form 4 XML)"),
    max_chars: int = Query(100000, ge=1000, le=1000000, description="Max characters to return"),
):
    """Fetch and extract clean text from a specific SEC filing by accession number."""
    cik = await get_cik_from_ticker(ticker)
    text = await fetch_filing_text(cik, accession_number, form_type)

    return {
        "ticker": ticker.upper(),
        "cik": cik,
        "accession_number": accession_number,
        "form_type": form_type or "unknown",
        "total_chars": len(text),
        "truncated": len(text) > max_chars,
        "text": text[:max_chars],
    }


# ───────────────────────────────────────────── Latest Filing Text
@app.get("/filing/latest", summary="Get text from the most recent filing of a given type", tags=["Filing Text"])
async def get_latest_filing_text(
    ticker: str = Query(..., description="Company ticker, e.g. MSFT"),
    form_type: str = Query(..., description="Filing type: 10-K, 10-Q, 8-K, DEF 14A, 4, S-1"),
    max_chars: int = Query(100000, ge=1000, le=1000000, description="Max characters to return"),
):
    """Fetch the most recent filing of a given type and return its extracted text."""
    cik = await get_cik_from_ticker(ticker)
    data = await get_company_submissions(cik)
    recent = data.get("filings", {}).get("recent", {})

    filings = _build_filing_list(recent, cik, form_type, 1)
    if not filings:
        raise HTTPException(status_code=404, detail=f"No {form_type} filings found for {ticker.upper()}.")

    match = filings[0]
    text = await fetch_filing_text(
        cik, match["accession_number"], form_type,
        primary_doc_hint=match.get("primary_document") or "",
    )

    return {
        "ticker": ticker.upper(),
        "cik": cik,
        "company_name": data.get("name"),
        "form_type": match["form_type"],
        "filing_date": match["filing_date"],
        "accession_number": match["accession_number"],
        "primary_document": match.get("primary_document"),
        "filing_url": match["filing_url"],
        "total_chars": len(text),
        "truncated": len(text) > max_chars,
        "text": text[:max_chars],
    }


# ───────────────────────────────────────────── Section Extraction (10-K / 10-Q)
@app.get("/filing/section", summary="Extract a specific section from a 10-K or 10-Q", tags=["Filing Text"])
async def get_filing_section(
    ticker: str = Query(..., description="Company ticker"),
    form_type: str = Query("10-K", description="10-K or 10-Q"),
    section: str = Query(
        ...,
        description="Section name: business, risk_factors, properties, legal_proceedings, md_and_a, financials",
    ),
    accession_number: Optional[str] = Query(None, description="Specific accession number (omit for latest)"),
    max_chars: int = Query(100000, ge=1000, le=500000, description="Max characters to return"),
):
    """
    Extract a specific section from a 10-K or 10-Q filing.
    Uses regex-based heading detection to locate Item boundaries.
    """
    if section.lower() not in SECTION_PATTERNS_10K:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown section '{section}'. Available: {list(SECTION_PATTERNS_10K.keys())}",
        )

    cik = await get_cik_from_ticker(ticker)

    if not accession_number:
        data = await get_company_submissions(cik)
        recent = data.get("filings", {}).get("recent", {})
        filings = _build_filing_list(recent, cik, form_type, 1)
        if not filings:
            raise HTTPException(status_code=404, detail=f"No {form_type} filings found for {ticker.upper()}.")
        accession_number = filings[0]["accession_number"]
        _primary_doc = filings[0].get("primary_document") or ""
    else:
        _primary_doc = ""

    full_text = await fetch_filing_text(cik, accession_number, form_type, primary_doc_hint=_primary_doc)
    section_text = extract_section(full_text, section)

    if not section_text:
        return {
            "ticker": ticker.upper(),
            "section": section,
            "warning": f"Could not locate section '{section}' via heading patterns. Returning full text.",
            "total_chars": len(full_text),
            "truncated": len(full_text) > max_chars,
            "text": full_text[:max_chars],
        }

    return {
        "ticker": ticker.upper(),
        "cik": cik,
        "form_type": form_type,
        "section": section,
        "accession_number": accession_number,
        "section_chars": len(section_text),
        "truncated": len(section_text) > max_chars,
        "text": section_text[:max_chars],
    }


# ───────────────────────────────────────────── Bulk Latest Filings
@app.get("/filing/bulk-latest", summary="Latest filing text for all key form types", tags=["Filing Text"])
async def get_bulk_latest(
    ticker: str = Query(..., description="Company ticker"),
    form_types: str = Query(
        "10-K,10-Q,8-K,DEF 14A,4,S-1",
        description="Comma-separated form types to fetch",
    ),
    max_chars_each: int = Query(20000, ge=1000, le=200000, description="Max chars per filing"),
):
    """
    Fetch the most recent filing of each requested form type in parallel.
    Great for getting a full snapshot of a company's latest disclosures.
    """
    cik = await get_cik_from_ticker(ticker)
    data = await get_company_submissions(cik)
    recent = data.get("filings", {}).get("recent", {})

    requested_types = [ft.strip() for ft in form_types.split(",") if ft.strip()]

    async def _fetch_one(ft: str) -> dict:
        filings = _build_filing_list(recent, cik, ft, 1)
        if not filings:
            return {"form_type": ft, "status": "not_found"}
        match = filings[0]
        try:
            text = await fetch_filing_text(
                cik, match["accession_number"], ft,
                primary_doc_hint=match.get("primary_document") or "",
            )
            return {
                "form_type": ft,
                "status": "ok",
                "filing_date": match["filing_date"],
                "accession_number": match["accession_number"],
                "filing_url": match["filing_url"],
                "total_chars": len(text),
                "truncated": len(text) > max_chars_each,
                "text": text[:max_chars_each],
            }
        except Exception as exc:
            return {"form_type": ft, "status": "error", "detail": str(exc)}

    # Fetch all in parallel (rate limiter will serialize as needed)
    results = await asyncio.gather(*[_fetch_one(ft) for ft in requested_types])

    return {
        "ticker": ticker.upper(),
        "cik": cik,
        "company_name": data.get("name"),
        "filings": {r["form_type"]: r for r in results},
    }


# ───────────────────────────────────────────── Full-Text Search
@app.get("/search", summary="Full-text search across EDGAR filings", tags=["Search"])
async def search_filings(
    q: str = Query(..., description="Search query text"),
    form_type: Optional[str] = Query(None, description="Filter by form type, e.g. 10-K"),
    ticker: Optional[str] = Query(None, description="Filter by company ticker"),
    date_from: Optional[str] = Query(None, description="Start date YYYY-MM-DD"),
    date_to: Optional[str] = Query(None, description="End date YYYY-MM-DD"),
    count: int = Query(10, ge=1, le=50, description="Number of results"),
):
    """
    Search EDGAR full-text search (EFTS) for filings matching a query.
    Useful for finding filings that mention specific topics, transactions, etc.
    """
    params: Dict[str, Any] = {"q": q, "from": 0, "size": count}
    if form_type:
        params["forms"] = form_type
    if ticker:
        cik = await get_cik_from_ticker(ticker)
        # Use CIK number for more precise entity filtering
        params["q"] = f"{q} AND entityId:\"CIK{cik}\""
    if date_from:
        params["dateRange"] = "custom"
        params["startdt"] = date_from
    if date_to:
        params.setdefault("dateRange", "custom")
        params["enddt"] = date_to

    url = f"{EFTS_BASE}/search-index"
    r = await _sec_get(url, params=params)
    if r.status_code != 200:
        raise HTTPException(status_code=502, detail="EDGAR full-text search failed.")

    data = r.json()
    hits = data.get("hits", {}).get("hits", [])

    results = []
    for hit in hits:
        src = hit.get("_source", {})
        results.append({
            "entity_name": src.get("entity_name"),
            "file_num": src.get("file_num"),
            "form_type": src.get("form_type"),
            "filing_date": src.get("period_of_report") or src.get("file_date"),
            "accession_number": hit.get("_id"),
            "snippet": " ... ".join(
                hit.get("highlight", {}).get("content", [])[:3]
            ) if hit.get("highlight") else None,
        })

    return {
        "query": q,
        "total_hits": data.get("hits", {}).get("total", {}).get("value", 0),
        "returned": len(results),
        "results": results,
    }


# ═══════════════════════════════════════════════════════════════
# SERVE FRONTEND (production — built React app from frontend/dist)
# ═══════════════════════════════════════════════════════════════

FRONTEND_DIR = Path(__file__).parent / "frontend" / "dist"

if FRONTEND_DIR.is_dir():
    # Serve static assets (JS, CSS, images) under /assets
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIR / "assets"), name="static-assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def serve_frontend(full_path: str):
        """Catch-all: serve index.html for SPA client-side routing."""
        file_path = FRONTEND_DIR / full_path
        if file_path.is_file():
            return FileResponse(file_path)
        return FileResponse(FRONTEND_DIR / "index.html")
