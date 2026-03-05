import React, { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { getBulkLatest } from '../api'

const FORM_COLORS = { '10-K': 'tag-10-K', '10-Q': 'tag-10-Q', '8-K': 'tag-8-K', 'DEF 14A': 'tag-DEF-14A', '4': 'tag-4', 'S-1': 'tag-S-1' }

export default function BulkView() {
  const { ticker } = useParams()
  const navigate = useNavigate()
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [expanded, setExpanded] = useState(null)

  useEffect(() => {
    loadBulk()
  }, [ticker])

  async function loadBulk() {
    setLoading(true)
    setError(null)
    try {
      const result = await getBulkLatest(ticker, 30000)
      setData(result)
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  if (loading) {
    return (
      <div className="loading-container">
        <div className="spinner spinner-lg" />
        <span>Fetching all filing types for {ticker}...</span>
        <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>
          This downloads 6 filings in parallel — may take 10-15 seconds
        </span>
      </div>
    )
  }

  if (error) {
    return (
      <div className="empty-state">
        <div className="icon">⚠️</div>
        <h3>Error</h3>
        <p style={{ color: 'var(--danger)' }}>{error}</p>
        <button className="btn btn-primary" style={{ marginTop: 16 }} onClick={() => navigate('/')}>← Back</button>
      </div>
    )
  }

  const filings = data?.filings || {}

  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 16, marginBottom: 24 }}>
        <button className="btn btn-secondary btn-sm" onClick={() => navigate(`/company/${ticker}`)}>← Back to {ticker}</button>
        <div className="page-header" style={{ marginBottom: 0 }}>
          <h2>📦 Bulk Filing Snapshot — {ticker}</h2>
          <p>{data?.company_name}</p>
        </div>
      </div>

      {/* Summary grid */}
      <div className="grid-3" style={{ marginBottom: 24 }}>
        {Object.entries(filings).map(([ft, info]) => (
          <div key={ft} className="card" style={{ cursor: info.status === 'ok' ? 'pointer' : 'default' }}
               onClick={() => info.status === 'ok' && setExpanded(expanded === ft ? null : ft)}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
              <span className={`tag ${FORM_COLORS[ft] || ''}`}>{ft}</span>
              {info.status === 'ok' && <span className="status-badge status-ok">✓ Found</span>}
              {info.status === 'not_found' && <span className="status-badge status-notfound">— Not filed</span>}
              {info.status === 'error' && <span className="status-badge status-error">✗ Error</span>}
            </div>
            {info.status === 'ok' && (
              <div>
                <div style={{ fontSize: 13, color: 'var(--text-muted)' }}>
                  Filed: {info.filing_date} · {(info.total_chars || 0).toLocaleString()} chars
                  {info.truncated && ' (truncated)'}
                </div>
              </div>
            )}
            {info.status === 'ok' && (
              <div style={{ marginTop: 8, fontSize: 12, color: 'var(--accent)' }}>
                {expanded === ft ? '▼ Click to collapse' : '▶ Click to expand text'}
              </div>
            )}
          </div>
        ))}
      </div>

      {/* Expanded text viewer */}
      {expanded && filings[expanded]?.text && (
        <div>
          <div className="card" style={{ marginBottom: 16 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div>
                <span className={`tag ${FORM_COLORS[expanded] || ''}`} style={{ marginRight: 12 }}>{expanded}</span>
                <span style={{ fontWeight: 600 }}>{filings[expanded].filing_date}</span>
                <span style={{ color: 'var(--text-muted)', marginLeft: 12, fontSize: 13 }}>
                  {(filings[expanded].total_chars || 0).toLocaleString()} characters
                </span>
              </div>
              <div style={{ display: 'flex', gap: 8 }}>
                <button
                  className="btn btn-secondary btn-sm"
                  onClick={() => {
                    navigator.clipboard.writeText(filings[expanded].text)
                    alert('Copied!')
                  }}
                >
                  📋 Copy
                </button>
                <button
                  className="btn btn-secondary btn-sm"
                  onClick={() => {
                    const blob = new Blob([filings[expanded].text], { type: 'text/plain' })
                    const a = document.createElement('a')
                    a.href = URL.createObjectURL(blob)
                    a.download = `${ticker}_${expanded}_${filings[expanded].filing_date}.txt`
                    a.click()
                  }}
                >
                  💾 Download
                </button>
                <button className="btn btn-danger btn-sm" onClick={() => setExpanded(null)}>
                  ✕ Close
                </button>
              </div>
            </div>
          </div>
          <div className="text-viewer">{filings[expanded].text}</div>
        </div>
      )}
    </div>
  )
}
