import React, { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { getLatestFiling, getFilingText } from '../api'

export default function FilingViewer() {
  const navigate = useNavigate()
  const [ticker, setTicker] = useState('')
  const [formType, setFormType] = useState('10-K')
  const [accession, setAccession] = useState('')
  const [maxChars, setMaxChars] = useState(100000)
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)

  async function fetchLatest() {
    if (!ticker.trim()) return
    setLoading(true)
    setError(null)
    try {
      const data = await getLatestFiling(ticker.trim(), formType, maxChars)
      setResult(data)
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  async function fetchByAccession() {
    if (!ticker.trim() || !accession.trim()) return
    setLoading(true)
    setError(null)
    try {
      const data = await getFilingText(ticker.trim(), accession.trim(), formType, maxChars)
      setResult(data)
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
          <h2>Filing Viewer</h2>
          <p>Fetch and read filing text directly</p>
        </div>
      </div>

      <div className="card" style={{ marginBottom: 24 }}>
        <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', alignItems: 'flex-end' }}>
          <div>
            <label style={{ display: 'block', fontSize: 12, color: 'var(--text-muted)', marginBottom: 4 }}>Ticker</label>
            <input
              className="search-bar"
              style={{ width: 140, padding: '10px 14px', paddingLeft: 14 }}
              placeholder="AAPL"
              value={ticker}
              onChange={(e) => setTicker(e.target.value.toUpperCase())}
            />
          </div>
          <div>
            <label style={{ display: 'block', fontSize: 12, color: 'var(--text-muted)', marginBottom: 4 }}>Form Type</label>
            <select className="select" value={formType} onChange={(e) => setFormType(e.target.value)}>
              <option value="10-K">10-K</option>
              <option value="10-Q">10-Q</option>
              <option value="8-K">8-K</option>
              <option value="DEF 14A">DEF 14A</option>
              <option value="4">Form 4</option>
              <option value="S-1">S-1</option>
            </select>
          </div>
          <div>
            <label style={{ display: 'block', fontSize: 12, color: 'var(--text-muted)', marginBottom: 4 }}>Max Chars</label>
            <select className="select" value={maxChars} onChange={(e) => setMaxChars(Number(e.target.value))}>
              <option value={10000}>10K</option>
              <option value={50000}>50K</option>
              <option value={100000}>100K</option>
              <option value={500000}>500K</option>
            </select>
          </div>
          <button className="btn btn-primary" onClick={fetchLatest} disabled={loading || !ticker.trim()}>
            {loading ? <span className="spinner" /> : null}
            Fetch Latest
          </button>
        </div>

        <div style={{ marginTop: 16, paddingTop: 16, borderTop: '1px solid var(--border)', display: 'flex', gap: 12, flexWrap: 'wrap', alignItems: 'flex-end' }}>
          <div style={{ flex: 1, minWidth: 250 }}>
            <label style={{ display: 'block', fontSize: 12, color: 'var(--text-muted)', marginBottom: 4 }}>Or fetch by Accession Number</label>
            <input
              className="search-bar"
              style={{ padding: '10px 14px', paddingLeft: 14 }}
              placeholder="0000320193-23-000106"
              value={accession}
              onChange={(e) => setAccession(e.target.value)}
            />
          </div>
          <button className="btn btn-secondary" onClick={fetchByAccession} disabled={loading || !ticker.trim() || !accession.trim()}>
            Fetch by Accession
          </button>
        </div>
      </div>

      {error && (
        <div className="card" style={{ borderColor: 'var(--danger)', marginBottom: 16 }}>
          <span style={{ color: 'var(--danger)' }}>⚠️ {error}</span>
        </div>
      )}

      {result && (
        <div>
          <div className="card" style={{ marginBottom: 16 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 12 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                <span style={{ fontWeight: 700, fontSize: 18 }}>{result.ticker}</span>
                <span className="tag tag-10-K">{result.form_type}</span>
                {result.filing_date && <span style={{ color: 'var(--text-muted)' }}>{result.filing_date}</span>}
                <span style={{ color: 'var(--text-muted)', fontSize: 13 }}>
                  {(result.total_chars || 0).toLocaleString()} chars
                  {result.truncated && ' (truncated)'}
                </span>
              </div>
              <div style={{ display: 'flex', gap: 8 }}>
                <button
                  className="btn btn-secondary btn-sm"
                  onClick={() => {
                    navigator.clipboard.writeText(result.text)
                    alert('Copied!')
                  }}
                >
                  📋 Copy
                </button>
                <button
                  className="btn btn-secondary btn-sm"
                  onClick={() => {
                    const blob = new Blob([result.text], { type: 'text/plain' })
                    const a = document.createElement('a')
                    a.href = URL.createObjectURL(blob)
                    a.download = `${result.ticker}_${result.form_type}.txt`
                    a.click()
                  }}
                >
                  💾 Download
                </button>
              </div>
            </div>
          </div>
          <div className="text-viewer">{result.text}</div>
        </div>
      )}
    </div>
  )
}
