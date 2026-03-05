"""
In-process smoke-test for SEC EDGAR Filing API using FastAPI TestClient.
No need to start uvicorn separately — TestClient runs the app in-process.
"""
import sys, time

# Use synchronous TestClient (uses httpx under the hood)
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)
PASS = 0
FAIL = 0

def test(label, method, url, expect_key=None, expect_status=200):
    global PASS, FAIL
    print(f"\n{'='*60}")
    print(f"TEST: {label}")
    print(f"  {method.upper()} {url}")
    try:
        r = client.get(url) if method == "get" else client.post(url)
        print(f"  Status: {r.status_code}")
        if r.status_code != expect_status:
            print(f"  FAIL - expected status {expect_status}, got {r.status_code}")
            try:
                print(f"  Response: {r.json()}")
            except:
                print(f"  Response: {r.text[:500]}")
            FAIL += 1
            return None
        data = r.json()
        if expect_key and expect_key not in data:
            print(f"  FAIL - key '{expect_key}' not in response")
            FAIL += 1
            return data
        # Print a summary of top-level keys
        for k, v in data.items():
            val_str = str(v)
            if len(val_str) > 200:
                val_str = val_str[:200] + "..."
            print(f"  {k}: {val_str}")
        print(f"  PASS")
        PASS += 1
        return data
    except Exception as e:
        print(f"  FAIL - {type(e).__name__}: {e}")
        FAIL += 1
        return None


print("=" * 60)
print("SEC EDGAR Filing API - In-Process Smoke Tests")
print("=" * 60)

# 1. Root endpoint
test("Root / API Info", "get", "/", expect_key="supported_form_types")

# 2. Supported forms
test("GET /forms", "get", "/forms", expect_key="supported_forms")

# 3. Company info - Apple
data = test("Company info AAPL", "get", "/company/AAPL", expect_key="company_name")

# 4. List 10-K filings
data = test("List 10-K filings AAPL", "get", "/filings/AAPL?form_type=10-K&count=3", expect_key="filings")

# 5. Latest 10-K text
data = test("Latest 10-K text AAPL", "get", "/filing/latest?ticker=AAPL&form_type=10-K&max_chars=5000", expect_key="text")
if data:
    print(f"\n  >>> First 300 chars of 10-K text:\n  {data['text'][:300]}")

# 6. Latest 10-Q
data = test("Latest 10-Q text AAPL", "get", "/filing/latest?ticker=AAPL&form_type=10-Q&max_chars=5000", expect_key="text")

# 7. Latest 8-K
data = test("Latest 8-K text AAPL", "get", "/filing/latest?ticker=AAPL&form_type=8-K&max_chars=5000", expect_key="text")

# 8. Latest DEF 14A (Proxy Statement)
data = test("Latest DEF 14A AAPL", "get", "/filing/latest?ticker=AAPL&form_type=DEF%2014A&max_chars=5000", expect_key="text")

# 9. Latest Form 4 (insider transactions - XML parsing)
data = test("Latest Form 4 AAPL", "get", "/filing/latest?ticker=AAPL&form_type=4&max_chars=5000", expect_key="text")
if data:
    print(f"\n  >>> First 500 chars of Form 4:\n  {data['text'][:500]}")

# 10. Section extraction - risk_factors from 10-K
data = test("Section: risk_factors 10-K AAPL", "get", "/filing/section?ticker=AAPL&form_type=10-K&section=risk_factors&max_chars=3000", expect_key="text")
if data:
    print(f"\n  >>> First 300 chars of risk_factors:\n  {data['text'][:300]}")

# 11. Bulk latest - all form types
data = test("Bulk latest all types AAPL", "get", "/filing/bulk-latest?ticker=AAPL&max_chars_each=2000", expect_key="filings")
if data and "filings" in data:
    print(f"\n  >>> Bulk results summary:")
    for ft, info in data["filings"].items():
        status = info.get("status", "?")
        chars = info.get("total_chars", 0)
        print(f"    {ft}: status={status}, total_chars={chars}")

# 12. Search
data = test("Search: iPhone AAPL", "get", "/search?q=iPhone&ticker=AAPL&count=3", expect_key="results")

# 13. Company info - Microsoft
data = test("Company info MSFT", "get", "/company/MSFT", expect_key="company_name")

# 14. Filing text by specific accession (use one from earlier list if available)
# Get a known accession from the 10-K filing list
known = test("List 8-K MSFT", "get", "/filings/MSFT?form_type=8-K&count=1", expect_key="filings")
if known and known.get("filings"):
    acc = known["filings"][0]["accession_number"]
    test(f"Filing text by accession MSFT {acc}", "get", f"/filing/text?ticker=MSFT&accession_number={acc}&form_type=8-K&max_chars=3000", expect_key="text")

# 15. Invalid ticker
test("Invalid ticker XYZXYZ", "get", "/company/XYZXYZ", expect_status=404)

print(f"\n{'='*60}")
print(f"RESULTS: {PASS} passed, {FAIL} failed out of {PASS+FAIL} tests")
print(f"{'='*60}")

if FAIL > 0:
    sys.exit(1)
