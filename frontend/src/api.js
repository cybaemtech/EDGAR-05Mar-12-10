/* API helper — talks to FastAPI backend */

// In dev mode (Vite), /api is proxied to localhost:8000 with prefix stripped.
// In production, frontend is served by FastAPI directly — no prefix needed.
const API_BASE = import.meta.env.DEV ? '/api' : '';

async function apiFetch(path, params = {}) {
  const url = new URL(`${API_BASE}${path}`, window.location.origin);
  Object.entries(params).forEach(([k, v]) => {
    if (v !== undefined && v !== null && v !== '') {
      url.searchParams.set(k, v);
    }
  });

  const res = await fetch(url.toString());
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `HTTP ${res.status}`);
  }
  return res.json();
}

export async function getCompanyInfo(ticker) {
  return apiFetch(`/company/${encodeURIComponent(ticker)}`);
}

export async function getFilings(ticker, formType, count = 10) {
  return apiFetch(`/filings/${encodeURIComponent(ticker)}`, {
    form_type: formType,
    count,
  });
}

export async function getLatestFiling(ticker, formType, maxChars = 100000) {
  return apiFetch('/filing/latest', {
    ticker,
    form_type: formType,
    max_chars: maxChars,
  });
}

export async function getFilingText(ticker, accessionNumber, formType = '', maxChars = 100000) {
  return apiFetch('/filing/text', {
    ticker,
    accession_number: accessionNumber,
    form_type: formType,
    max_chars: maxChars,
  });
}

export async function getFilingSection(ticker, formType, section, maxChars = 100000) {
  return apiFetch('/filing/section', {
    ticker,
    form_type: formType,
    section,
    max_chars: maxChars,
  });
}

export async function getBulkLatest(ticker, maxCharsEach = 20000) {
  return apiFetch('/filing/bulk-latest', {
    ticker,
    max_chars_each: maxCharsEach,
  });
}

export async function searchFilings(query, options = {}) {
  return apiFetch('/search', {
    q: query,
    ...options,
  });
}

export async function getSupportedForms() {
  return apiFetch('/forms');
}
