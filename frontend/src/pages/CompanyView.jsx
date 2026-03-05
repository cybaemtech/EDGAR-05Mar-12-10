import React, { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { getCompanyInfo, getFilings, getLatestFiling } from '../api'

const FORM_TYPES = ['10-K', '10-Q', '8-K', 'DEF 14A', '4', 'S-1']
const FORM_COLORS = { '10-K': 'tag-10-K', '10-Q': 'tag-10-Q', '8-K': 'tag-8-K', 'DEF 14A': 'tag-DEF-14A', '4': 'tag-4', 'S-1': 'tag-S-1' }

export default function CompanyView() {
  const { ticker } = useParams()
  const navigate = useNavigate()
  const [company, setCompany] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [activeTab, setActiveTab] = useState('overview')
  const [filings, setFilings] = useState([])
  const [filingsLoading, setFilingsLoading] = useState(false)
  const [selectedForm, setSelectedForm] = useState('10-K')
  const [filingText, setFilingText] = useState(null)
  const [textLoading, setTextLoading] = useState(false)
  const [textError, setTextError] = useState(null)

  useEffect(() => {
    loadCompany()
  }, [ticker])

  async function loadCompany() {
    setLoading(true)
    setError(null)
    try {
      const data = await getCompanyInfo(ticker)
      setCompany(data)
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  async function loadFilings(formType) {
    setSelectedForm(formType)
    setFilingsLoading(true)
    setFilingText(null)
    try {
      const data = await getFilings(ticker, formType, 10)
      setFilings(data.filings || [])
    } catch {
      setFilings([])
    } finally {
      setFilingsLoading(false)
    }
  }

  async function loadLatestText(formType) {
    setTextLoading(true)
    setTextError(null)
    try {
      const data = await getLatestFiling(ticker, formType, 50000)
      setFilingText(data)
    } catch (e) {
      setTextError(e.message)
    } finally {
      setTextLoading(false)
    }
  }

  if (loading) {
    return (
      <div className="loading-container">
        <div className="spinner spinner-lg" />
        <span>Loading {ticker}...</span>
      </div>
    )
  }

  if (error) {
    return (
      <div className="empty-state">
        <div className="icon">⚠️</div>
        <h3>Error loading {ticker}</h3>
        <p style={{ color: 'var(--danger)' }}>{error}</p>
        <button className="btn btn-primary" style={{ marginTop: 16 }} onClick={() => navigate('/')}>
          ← Back to Search
        </button>
      </div>
    )
  }

  const recentTypes = company?.recent_filings_by_type || {}

  return (
    <div>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 16, marginBottom: 8 }}>
        <button className="btn btn-secondary btn-sm" onClick={() => navigate('/')}>← Back</button>
        <div className="page-header" style={{ marginBottom: 0 }}>
          <h2>{company.company_name}</h2>
          <p>
            <span style={{ fontWeight: 600, color: 'var(--accent)' }}>{company.ticker}</span>
            {' · CIK '}
            {company.cik}
            {company.exchanges?.length > 0 && ` · ${company.exchanges.join(', ')}`}
          </p>
        </div>
      </div>

      {/* Tabs */}
      <div className="tabs">
        {['overview', 'filings', 'view-text', 'bulk'].map((tab) => (
          <button
            key={tab}
            className={`tab ${activeTab === tab ? 'active' : ''}`}
            onClick={() => setActiveTab(tab)}
          >
            {tab === 'overview' && '📊 Overview'}
            {tab === 'filings' && '📋 Filing List'}
            {tab === 'view-text' && '📄 View Filing Text'}
            {tab === 'bulk' && '📦 Bulk Snapshot'}
          </button>
        ))}
      </div>

      {/* Tab: Overview */}
      {activeTab === 'overview' && (
        <div>
          <div className="grid-2" style={{ marginBottom: 24 }}>
            <div className="card">
              <h3 style={{ fontSize: 15, fontWeight: 600, marginBottom: 16 }}>Company Details</h3>
              <div className="meta-list">
                <div className="meta-item">
                  <span className="meta-label">Industry (SIC)</span>
                  <span className="meta-value">{company.sic_description || '—'}</span>
                </div>
                <div className="meta-item">
                  <span className="meta-label">SIC Code</span>
                  <span className="meta-value">{company.sic || '—'}</span>
                </div>
                <div className="meta-item">
                  <span className="meta-label">State</span>
                  <span className="meta-value">{company.state_of_incorporation || '—'}</span>
                </div>
                <div className="meta-item">
                  <span className="meta-label">Fiscal Year End</span>
                  <span className="meta-value">{company.fiscal_year_end || '—'}</span>
                </div>
                <div className="meta-item">
                  <span className="meta-label">Entity Type</span>
                  <span className="meta-value">{company.entity_type || '—'}</span>
                </div>
                <div className="meta-item">
                  <span className="meta-label">EIN</span>
                  <span className="meta-value">{company.ein || '—'}</span>
                </div>
              </div>
            </div>

            <div className="card">
              <h3 style={{ fontSize: 15, fontWeight: 600, marginBottom: 16 }}>Recent Filing Counts</h3>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                {FORM_TYPES.map((ft) => {
                  const count = (recentTypes[ft] || []).length
                  return (
                    <div key={ft} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                      <span className={`tag ${FORM_COLORS[ft]}`}>{ft}</span>
                      <span style={{ fontSize: 14, fontWeight: 600 }}>
                        {count > 0 ? `${count} recent` : '—'}
                      </span>
                    </div>
                  )
                })}
              </div>
            </div>
          </div>

          <div className="card">
            <h3 style={{ fontSize: 15, fontWeight: 600, marginBottom: 16 }}>Quick Actions</h3>
            <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
              <button className="btn btn-primary" onClick={() => { setActiveTab('view-text'); loadLatestText('10-K') }}>
                📋 Read Latest 10-K
              </button>
              <button className="btn btn-secondary" onClick={() => { setActiveTab('view-text'); loadLatestText('10-Q') }}>
                📄 Read Latest 10-Q
              </button>
              <button className="btn btn-secondary" onClick={() => { setActiveTab('view-text'); loadLatestText('8-K') }}>
                ⚡ Read Latest 8-K
              </button>
              <button className="btn btn-secondary" onClick={() => navigate(`/bulk/${ticker}`)}>
                📦 Bulk Snapshot (All Types)
              </button>
              <a
                className="btn btn-secondary"
                href={`https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK=${company.cik}&type=&dateb=&owner=include&count=40`}
                target="_blank"
                rel="noopener"
              >
                🌐 View on SEC.gov
              </a>
            </div>
          </div>
        </div>
      )}

      {/* Tab: Filings */}
      {activeTab === 'filings' && (
        <div>
          <div style={{ display: 'flex', gap: 12, marginBottom: 20, flexWrap: 'wrap' }}>
            {FORM_TYPES.map((ft) => (
              <button
                key={ft}
                className={`btn ${selectedForm === ft ? 'btn-primary' : 'btn-secondary'} btn-sm`}
                onClick={() => loadFilings(ft)}
              >
                {ft}
              </button>
            ))}
          </div>

          {filingsLoading ? (
            <div className="loading-container">
              <div className="spinner" />
              <span>Loading {selectedForm} filings...</span>
            </div>
          ) : filings.length === 0 ? (
            <div className="empty-state">
              <div className="icon">📭</div>
              <h3>No {selectedForm} filings found</h3>
              <p>Select a filing type above to browse</p>
            </div>
          ) : (
            <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Type</th>
                    <th>Filing Date</th>
                    <th>Accession Number</th>
                    <th>Document</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {filings.map((f) => (
                    <tr key={f.accession_number}>
                      <td><span className={`tag ${FORM_COLORS[f.form_type] || ''}`}>{f.form_type}</span></td>
                      <td>{f.filing_date}</td>
                      <td style={{ fontFamily: 'monospace', fontSize: 12 }}>{f.accession_number}</td>
                      <td style={{ fontSize: 13 }}>{f.primary_document || '—'}</td>
                      <td>
                        <div style={{ display: 'flex', gap: 8 }}>
                          <button
                            className="btn btn-primary btn-sm"
                            onClick={() => {
                              setActiveTab('view-text')
                              setTextLoading(true)
                              setTextError(null)
                              import('../api').then(({ getFilingText }) =>
                                getFilingText(ticker, f.accession_number, f.form_type, 50000)
                                  .then(setFilingText)
                                  .catch((e) => setTextError(e.message))
                                  .finally(() => setTextLoading(false))
                              )
                            }}
                          >
                            Read
                          </button>
                          <a
                            className="btn btn-secondary btn-sm"
                            href={f.filing_url}
                            target="_blank"
                            rel="noopener"
                          >
                            SEC →
                          </a>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* Tab: View Text */}
      {activeTab === 'view-text' && (
        <div>
          <div style={{ display: 'flex', gap: 12, marginBottom: 20, alignItems: 'center', flexWrap: 'wrap' }}>
            <span style={{ fontSize: 14, color: 'var(--text-muted)' }}>Quick fetch latest:</span>
            {FORM_TYPES.map((ft) => (
              <button
                key={ft}
                className="btn btn-secondary btn-sm"
                onClick={() => loadLatestText(ft)}
                disabled={textLoading}
              >
                {ft}
              </button>
            ))}
          </div>

          {textLoading ? (
            <div className="loading-container">
              <div className="spinner spinner-lg" />
              <span>Downloading and extracting filing text from SEC EDGAR...</span>
              <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>This may take a few seconds for large filings</span>
            </div>
          ) : textError ? (
            <div className="card" style={{ borderColor: 'var(--danger)' }}>
              <span style={{ color: 'var(--danger)' }}>⚠️ {textError}</span>
            </div>
          ) : filingText ? (
            <div>
              <div className="card" style={{ marginBottom: 16 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 12 }}>
                  <div>
                    <span className={`tag ${FORM_COLORS[filingText.form_type] || ''}`} style={{ marginRight: 12 }}>
                      {filingText.form_type}
                    </span>
                    <span style={{ fontWeight: 600 }}>{filingText.filing_date || ''}</span>
                    <span style={{ color: 'var(--text-muted)', marginLeft: 12, fontSize: 13 }}>
                      {(filingText.total_chars || 0).toLocaleString()} characters
                      {filingText.truncated && ' (truncated)'}
                    </span>
                  </div>
                  <div style={{ display: 'flex', gap: 8 }}>
                    <button
                      className="btn btn-secondary btn-sm"
                      onClick={() => {
                        navigator.clipboard.writeText(filingText.text)
                        alert('Text copied to clipboard!')
                      }}
                    >
                      📋 Copy
                    </button>
                    <button
                      className="btn btn-secondary btn-sm"
                      onClick={() => {
                        const blob = new Blob([filingText.text], { type: 'text/plain' })
                        const url = URL.createObjectURL(blob)
                        const a = document.createElement('a')
                        a.href = url
                        a.download = `${ticker}_${filingText.form_type}_${filingText.filing_date || 'filing'}.txt`
                        a.click()
                        URL.revokeObjectURL(url)
                      }}
                    >
                      💾 Download .txt
                    </button>
                  </div>
                </div>
              </div>
              <div className="text-viewer">{filingText.text}</div>
            </div>
          ) : (
            <div className="empty-state">
              <div className="icon">📄</div>
              <h3>Select a filing type to view</h3>
              <p>Click any button above to fetch the latest filing text</p>
            </div>
          )}
        </div>
      )}

      {/* Tab: Bulk */}
      {activeTab === 'bulk' && (
        <div className="empty-state">
          <div className="icon">📦</div>
          <h3>Bulk Snapshot</h3>
          <p>View all filing types at once</p>
          <button
            className="btn btn-primary"
            style={{ marginTop: 16 }}
            onClick={() => navigate(`/bulk/${ticker}`)}
          >
            Open Bulk View
          </button>
        </div>
      )}
    </div>
  )
}
