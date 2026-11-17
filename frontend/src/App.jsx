import React from 'react'
import { Routes, Route } from 'react-router-dom'
import { AuthProvider } from './context/AuthContext'
import { AppProvider } from './context/AppContext'
import Home from './pages/Home'
import FullReport from './pages/FullReport'

export default function App() {
  return (
    <AuthProvider>
      <AppProvider>
        <Routes>
          <Route path="/"       element={<Home />} />
          <Route path="/report" element={<FullReport />} />
        </Routes>
      </AppProvider>
    </AuthProvider>
  )
}
