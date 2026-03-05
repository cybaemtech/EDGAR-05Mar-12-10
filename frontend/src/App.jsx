import React, { useState } from 'react'
import { HashRouter as Router, Routes, Route, useNavigate, useLocation } from 'react-router-dom'
import Sidebar from './components/Sidebar'
import Dashboard from './pages/Dashboard'
import CompanyView from './pages/CompanyView'
import FilingViewer from './pages/FilingViewer'
import BulkView from './pages/BulkView'
import SearchPage from './pages/SearchPage'

function AppLayout() {
  const navigate = useNavigate()
  const location = useLocation()

  return (
    <div className="app-container">
      <Sidebar currentPath={location.pathname} onNavigate={navigate} />
      <div className="main-content">
        <Routes>
          <Route path="/" element={<Dashboard onNavigate={navigate} />} />
          <Route path="/company/:ticker" element={<CompanyView />} />
          <Route path="/filing" element={<FilingViewer />} />
          <Route path="/bulk/:ticker" element={<BulkView />} />
          <Route path="/search" element={<SearchPage />} />
        </Routes>
      </div>
    </div>
  )
}

export default function App() {
  return (
    <Router>
      <AppLayout />
    </Router>
  )
}
