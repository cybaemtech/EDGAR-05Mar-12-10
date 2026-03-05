"""
Quick smoke-test for SEC EDGAR Filing API.
Run AFTER starting the server:  uvicorn main:app --host 127.0.0.1 --port 8000
"""

import httpx, json, sys, time

BASE = "http://127.0.0.1:8000"
PASS = 0
FAIL = 0

def test(label, url, expect_key=None, expect_status=200):
    global PASS, FAIL
    print(f"\n{'='*60}")
    print(f"TEST: {label}")
    print(f"  URL: {url}")
    try:
        r = httpx.get(url, timeout=60, follow_redirects=True)
        print(f"  Status: {r.status_code}")
        if r.status_code != expect_status:
            print(f"  ❌ FAIL — expected status {expect_status}")
            FAIL += 1
            return None
        data = r.json()
        if expect_key and expect_key not in data:
            print(f"  ❌ FAIL — key '{expect_key}' not in response")
            FAIL += 1
            return data
        # Print a summary
        for k, v in data.items():
            val_str = str(v)
            if len(val_str) > 200:
                val_str = val_str[:200] + "..."
            print(f"  {k}: {val_str}")
        print(f"  ✅ PASS")
        PASS += 1
        return data
    except Exception as e:
        print(f"  ❌ FAIL — {e}")
        FAIL += 1
        return None


print("SEC EDGAR Filing API — Smoke Tests")
print(f"Server: {BASE}")

# 1. Root endpoint
test("Root / API Info", f"{BASE}/", expect_key="supported_form_types")

# 2. Supported forms
test("GET /forms", f"{BASE}/forms", expect_key="supported_forms")

# 3. Company info — Apple
data = test("GET /company/AAPL", f"{BASE}/company/AAPL", expect_key="company_name")

# 4. List 10-K filings for Apple
data = test("GET /filings/AAPL?form_type=10-K", f"{BASE}/filings/AAPL?form_type=10-K&count=3", expect_key="filings")

# 5. Latest 10-K text for Apple
data = test("GET /filing/latest 10-K AAPL", f"{BASE}/filing/latest?ticker=AAPL&form_type=10-K&max_chars=5000", expect_key="text")
if data:
    print(f"  >>> First 300 chars of text: {data['text'][:300]}")

# 6. Latest 10-Q
data = test("GET /filing/latest 10-Q AAPL", f"{BASE}/filing/latest?ticker=AAPL&form_type=10-Q&max_chars=5000", expect_key="text")

# 7. Latest 8-K
data = test("GET /filing/latest 8-K AAPL", f"{BASE}/filing/latest?ticker=AAPL&form_type=8-K&max_chars=5000", expect_key="text")

# 8. Latest DEF 14A
data = test("GET /filing/latest DEF 14A AAPL", f"{BASE}/filing/latest?ticker=AAPL&form_type=DEF+14A&max_chars=5000", expect_key="text")

# 9. Latest Form 4 (insider transactions)
data = test("GET /filing/latest Form 4 AAPL", f"{BASE}/filing/latest?ticker=AAPL&form_type=4&max_chars=5000", expect_key="text")
if data:
    print(f"  >>> First 500 chars of Form 4 text:\n{data['text'][:500]}")

# 10. Section extraction — risk_factors from 10-K
data = test("GET /filing/section risk_factors AAPL", f"{BASE}/filing/section?ticker=AAPL&form_type=10-K&section=risk_factors&max_chars=3000", expect_key="text")
if data:
    print(f"  >>> First 300 chars of risk_factors: {data['text'][:300]}")

# 11. Bulk latest — all form types at once
data = test("GET /filing/bulk-latest AAPL", f"{BASE}/filing/bulk-latest?ticker=AAPL&max_chars_each=2000", expect_key="filings")
if data:
    for ft, info in data.get("filings", {}).items():
        status = info.get("status", "?")
        chars = info.get("total_chars", 0)
        print(f"    {ft}: status={status}, chars={chars}")

# 12. Search
data = test("GET /search q=iPhone", f"{BASE}/search?q=iPhone&ticker=AAPL&count=3", expect_key="results")

# 13. Company info — Berkshire Hathaway (from the user's example)
data = test("GET /company/BRK-B (Berkshire)", f"{BASE}/company/BRK-B", expect_key="company_name")

# If BRK-B fails, try BRK.B
if data is None:
    data = test("GET /company/BRK.B (Berkshire alt)", f"{BASE}/company/BRK.B", expect_key="company_name")

print(f"\n{'='*60}")
print(f"RESULTS: {PASS} passed, {FAIL} failed out of {PASS+FAIL} tests")
print(f"{'='*60}")
