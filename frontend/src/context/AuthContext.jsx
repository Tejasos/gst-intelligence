import React, { createContext, useContext, useState, useEffect } from 'react'
import { getMeApi, loginApi, registerApi, logoutApi } from '../api/client'

const AuthContext = createContext(null)

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null)
  const [token, setToken] = useState(() => localStorage.getItem('gst_auth_token'))
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const fetchUser = async () => {
      const storedToken = localStorage.getItem('gst_auth_token')
      if (!storedToken) {
        setLoading(false)
        return
      }
      try {
        const res = await getMeApi()
        setUser(res.data.user)
      } catch (err) {
        console.warn('Session verification failed, clearing token:', err)
        localStorage.removeItem('gst_auth_token')
        setToken(null)
        setUser(null)
      } finally {
        setLoading(false)
      }
    }
    fetchUser()
  }, [])

  const login = async (email, password) => {
    const res = await loginApi(email, password)
    const { token: newToken, user: newUser } = res.data
    localStorage.setItem('gst_auth_token', newToken)
    setToken(newToken)
    setUser(newUser)
    return newUser
  }

  const register = async (username, email, password) => {
    const res = await registerApi(username, email, password)
    const { token: newToken, user: newUser } = res.data
    localStorage.setItem('gst_auth_token', newToken)
    setToken(newToken)
    setUser(newUser)
    return newUser
  }

  const logout = async () => {
    try {
      await logoutApi()
    } catch (e) {
      // ignore
    } finally {
      localStorage.removeItem('gst_auth_token')
      setToken(null)
      setUser(null)
    }
  }

  return (
    <AuthContext.Provider value={{ user, token, loading, login, register, logout, isAuthenticated: !!user }}>
      {children}
    </AuthContext.Provider>
  )
}

export const useAuth = () => useContext(AuthContext)
