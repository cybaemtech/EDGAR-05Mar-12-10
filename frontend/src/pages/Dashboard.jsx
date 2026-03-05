import React, { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { getCompanyInfo } from '../api'

const QUICK_PICKS = [
  { ticker: 'AAPL', name: 'Apple Inc.' },
  { ticker: 'MSFT', name: 'Microsoft' },
  { ticker: 'GOOGL', name: 'Alphabet' },
  { ticker: 'AMZN', name: 'Amazon' },
  { ticker: 'META', name: 'Meta Platforms' },
  { ticker: 'JPM', name: 'JPMorgan Chase' },
  { ticker: 'BRK-B', name: 'Berkshire Hathaway' },
  { ticker: 'TSLA', name: 'Tesla' },
]

export default function Dashboard({ onNavigate }) {
  const [ticker, setTicker] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const navigate = useNavigate()

  async function handleSearch(searchTicker) {
    const t = (searchTicker || ticker).trim().toUpperCase()
    if (!t) return
    setLoading(true)
    setError(null)
    try {
      await getCompanyInfo(t) // verify it exists
      navigate(`/company/${t}`)
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div>
      <div className="page-header">
        <h2>SEC EDGAR Filing Explorer</h2>
        <p>Search any publicly-traded company to view their SEC filings</p>
      </div>

      {/* Search */}
      <div className="search-container">
        <span className="search-icon" style={{ fontSize: 20 }}>🔎</span>
        <input
          className="search-bar"
          type="text"
          placeholder="Enter company ticker (e.g., AAPL, MSFT, JPM)..."
          value={ticker}
          onChange={(e) => setTicker(e.target.value.toUpperCase())}
          onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
          disabled={loading}
        />
      </div>

      <div style={{ display: 'flex', gap: 12, marginBottom: 24, flexWrap: 'wrap' }}>
        <button
          className="btn btn-primary"
          onClick={() => handleSearch()}
          disabled={loading || !ticker.trim()}
        >
          {loading ? <span className="spinner" /> : null}
          {loading ? 'Looking up...' : 'Search Company'}
        </button>
        <button
          className="btn btn-secondary"
          onClick={() => navigate('/search')}
        >
          🔍 Full-Text Search
        </button>
      </div>

      {error && (
        <div className="card" style={{ borderColor: 'var(--danger)', marginBottom: 24 }}>
          <span style={{ color: 'var(--danger)' }}>⚠️ {error}</span>
        </div>
      )}

      {/* Quick picks */}
      <h3 style={{ fontSize: 16, fontWeight: 600, marginBottom: 16, color: 'var(--text-secondary)' }}>
        Popular Companies
      </h3>
      <div className="grid-3" style={{ marginBottom: 32 }}>
        {QUICK_PICKS.map((c) => (
          <div
            key={c.ticker}
            className="card"
            style={{ cursor: 'pointer' }}
            onClick={() => handleSearch(c.ticker)}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div>
                <div style={{ fontSize: 18, fontWeight: 700 }}>{c.ticker}</div>
                <div style={{ fontSize: 13, color: 'var(--text-muted)' }}>{c.name}</div>
              </div>
              <span style={{ fontSize: 24, opacity: 0.3 }}>→</span>
            </div>
          </div>
        ))}
      </div>

      {/* Info cards */}
      <h3 style={{ fontSize: 16, fontWeight: 600, marginBottom: 16, color: 'var(--text-secondary)' }}>
        Supported Filing Types
      </h3>
      <div className="grid-2">
        {[
          { form: '10-K', title: 'Annual Report', desc: 'Comprehensive overview with audited financial statements, business description, and risk factors.', color: 'var(--tag-10k)' },
          { form: '10-Q', title: 'Quarterly Report', desc: 'Unaudited financial statements for Q1-Q3. Contains interim financials and MD&A.', color: 'var(--tag-10q)' },
          { form: '8-K', title: 'Current Report', desc: 'Major unscheduled events: acquisitions, bankruptcy filings, leadership changes.', color: 'var(--tag-8k)' },
          { form: 'DEF 14A', title: 'Proxy Statement', desc: 'Shareholder vote info: board elections, executive compensation, governance.', color: 'var(--tag-def14a)' },
          { form: 'Form 4', title: 'Insider Transactions', desc: 'Directors, officers, and 10%+ owners reporting stock buys/sells.', color: 'var(--tag-form4)' },
          { form: 'S-1', title: 'IPO Registration', desc: 'Filed before an Initial Public Offering. Contains prospectus and financials.', color: 'var(--tag-s1)' },
        ].map((item) => (
          <div key={item.form} className="card">
            <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 8 }}>
              <span className={`tag tag-${item.form.replace(' ', '-')}`}>{item.form}</span>
              <span style={{ fontWeight: 600 }}>{item.title}</span>
            </div>
            <p style={{ fontSize: 13, color: 'var(--text-secondary)', lineHeight: 1.5 }}>{item.desc}</p>
          </div>
        ))}
      </div>
    </div>
  )
}
