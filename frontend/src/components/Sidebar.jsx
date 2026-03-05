import React from 'react'

const NAV_ITEMS = [
  { path: '/', icon: '🏠', label: 'Dashboard' },
  { path: '/search', icon: '🔍', label: 'Search Filings' },
]

export default function Sidebar({ currentPath, onNavigate }) {
  return (
    <div className="sidebar">
      <div className="sidebar-logo">
        <h1>
          <span className="logo-icon">📊</span>
          <span>SEC EDGAR</span>
        </h1>
        <p>Filing Explorer v2.0</p>
      </div>

      <nav className="sidebar-nav">
        <div className="nav-section-label">Navigation</div>
        {NAV_ITEMS.map((item) => (
          <button
            key={item.path}
            className={`nav-item ${currentPath === item.path ? 'active' : ''}`}
            onClick={() => onNavigate(item.path)}
          >
            <span style={{ fontSize: '16px' }}>{item.icon}</span>
            <span>{item.label}</span>
          </button>
        ))}

        <div className="nav-section-label" style={{ marginTop: 24 }}>Filing Types</div>
        {[
          { form: '10-K', icon: '📋', desc: 'Annual Report' },
          { form: '10-Q', icon: '📄', desc: 'Quarterly Report' },
          { form: '8-K', icon: '⚡', desc: 'Current Report' },
          { form: 'DEF 14A', icon: '🗳️', desc: 'Proxy Statement' },
          { form: '4', icon: '👤', desc: 'Insider Trades' },
          { form: 'S-1', icon: '🚀', desc: 'IPO Filing' },
        ].map((item) => (
          <div
            key={item.form}
            className="nav-item"
            style={{ cursor: 'default', opacity: 0.7, fontSize: 13 }}
          >
            <span>{item.icon}</span>
            <span>{item.form} – {item.desc}</span>
          </div>
        ))}
      </nav>

      <div style={{ padding: '16px 24px', borderTop: '1px solid var(--border)', fontSize: 11, color: 'var(--text-muted)' }}>
        Data from SEC EDGAR
      </div>
    </div>
  )
}
