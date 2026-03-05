import React, { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { searchFilings } from '../api'

export default function SearchPage() {
  const navigate = useNavigate()
  const [query, setQuery] = useState('')
  const [ticker, setTicker] = useState('')
  const [formType, setFormType] = useState('')
  const [dateFrom, setDateFrom] = useState('')
  const [dateTo, setDateTo] = useState('')
  const [results, setResults] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  async function handleSearch() {
    if (!query.trim()) return
    setLoading(true)
    setError(null)
    try {
      const data = await searchFilings(query, {
        ticker: ticker || undefined,
        form_type: formType || undefined,
        date_from: dateFrom || undefined,
        date_to: dateTo || undefined,
        count: 20,
      })
      setResults(data)
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 16, marginBottom: 24 }}>
        <button className="btn btn-secondary btn-sm" onClick={() => navigate('/')}>← Back</button>
        <div className="page-header" style={{ marginBottom: 0 }}>
          <h2>🔍 Full-Text Filing Search</h2>
          <p>Search across all SEC EDGAR filings using EFTS</p>
        </div>
      </div>

      <div className="card" style={{ marginBottom: 24 }}>
        <div style={{ display: 'flex', gap: 12, marginBottom: 16, flexWrap: 'wrap' }}>
          <div style={{ flex: 1, minWidth: 250 }}>
            <label style={{ display: 'block', fontSize: 12, color: 'var(--text-muted)', marginBottom: 4 }}>Search Query</label>
            <input
              className="search-bar"
              style={{ padding: '10px 14px', paddingLeft: 14 }}
              placeholder='e.g., "acquisition" or "revenue decline"'
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
            />
          </div>
        </div>

        <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', alignItems: 'flex-end' }}>
          <div>
            <label style={{ display: 'block', fontSize: 12, color: 'var(--text-muted)', marginBottom: 4 }}>Ticker (optional)</label>
            <input
              className="search-bar"
              style={{ width: 120, padding: '10px 14px', paddingLeft: 14 }}
              placeholder="AAPL"
              value={ticker}
              onChange={(e) => setTicker(e.target.value.toUpperCase())}
            />
          </div>
          <div>
            <label style={{ display: 'block', fontSize: 12, color: 'var(--text-muted)', marginBottom: 4 }}>Form Type</label>
            <select className="select" value={formType} onChange={(e) => setFormType(e.target.value)}>
              <option value="">All</option>
              <option value="10-K">10-K</option>
              <option value="10-Q">10-Q</option>
              <option value="8-K">8-K</option>
              <option value="DEF 14A">DEF 14A</option>
              <option value="4">Form 4</option>
              <option value="S-1">S-1</option>
            </select>
          </div>
          <div>
            <label style={{ display: 'block', fontSize: 12, color: 'var(--text-muted)', marginBottom: 4 }}>From Date</label>
            <input
              type="date"
              className="select"
              value={dateFrom}
              onChange={(e) => setDateFrom(e.target.value)}
            />
          </div>
          <div>
            <label style={{ display: 'block', fontSize: 12, color: 'var(--text-muted)', marginBottom: 4 }}>To Date</label>
            <input
              type="date"
              className="select"
              value={dateTo}
              onChange={(e) => setDateTo(e.target.value)}
            />
          </div>
          <button className="btn btn-primary" onClick={handleSearch} disabled={loading || !query.trim()}>
            {loading ? <span className="spinner" /> : '🔍'}
            {loading ? ' Searching...' : ' Search'}
          </button>
        </div>
      </div>

      {error && (
        <div className="card" style={{ borderColor: 'var(--danger)', marginBottom: 16 }}>
          <span style={{ color: 'var(--danger)' }}>⚠️ {error}</span>
        </div>
      )}

      {results && (
        <div>
          <div style={{ marginBottom: 16, fontSize: 14, color: 'var(--text-muted)' }}>
            Found <strong style={{ color: 'var(--text-primary)' }}>{results.total_hits?.toLocaleString()}</strong> results
            {results.returned > 0 && ` (showing ${results.returned})`}
          </div>

          {results.results?.length === 0 ? (
            <div className="empty-state">
              <div className="icon">📭</div>
              <h3>No results found</h3>
              <p>Try a different search query or broader filters</p>
            </div>
          ) : (
            <div>
              {results.results?.map((r, i) => (
                <div key={i} className="card">
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 8 }}>
                    <div>
                      <span style={{ fontWeight: 600, fontSize: 16, marginRight: 12 }}>
                        {r.entity_name || 'Unknown Entity'}
                      </span>
                      {r.form_type && <span className="tag tag-10-K">{r.form_type}</span>}
                    </div>
                    <span style={{ fontSize: 13, color: 'var(--text-muted)' }}>{r.filing_date || ''}</span>
                  </div>
                  {r.snippet && (
                    <div
                      style={{ fontSize: 13, color: 'var(--text-secondary)', lineHeight: 1.6, marginTop: 8 }}
                      dangerouslySetInnerHTML={{ __html: r.snippet }}
                    />
                  )}
                  <div style={{ marginTop: 12, fontSize: 12, color: 'var(--text-muted)' }}>
                    Accession: {r.accession_number || '—'} · File: {r.file_num || '—'}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {!results && !loading && (
        <div className="empty-state">
          <div className="icon">🔍</div>
          <h3>Search SEC Filings</h3>
          <p>Enter a search query above to find filings across the entire EDGAR database</p>
          <div style={{ marginTop: 20, display: 'flex', gap: 12, justifyContent: 'center', flexWrap: 'wrap' }}>
            {['acquisition target', 'revenue decline', 'insider purchase', 'material weakness', 'going concern'].map((q) => (
              <button
                key={q}
                className="btn btn-secondary btn-sm"
                onClick={() => { setQuery(q); }}
              >
                "{q}"
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
