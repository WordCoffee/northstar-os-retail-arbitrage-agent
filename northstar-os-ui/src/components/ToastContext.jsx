import { createContext, useContext, useState, useCallback } from 'react'

const ToastContext = createContext(null)

export function useToast() {
  const ctx = useContext(ToastContext)
  if (!ctx) throw new Error('useToast must be used within TOAST_PROVIDER')
  return ctx
}

export function TOAST_PROVIDER({ children }) {
  const [toasts, setToasts] = useState([])
  const toast = useCallback((msg, tone = 'ok') => {
    const id = Date.now() + Math.random()
    setToasts(prev => [...prev.slice(-4), { id, msg, tone }])
    setTimeout(() => setToasts(prev => prev.filter(t => t.id !== id)), 3200)
  }, [])
  return (
    <ToastContext.Provider value={{ toasts, toast }}>
      {children}
    </ToastContext.Provider>
  )
}