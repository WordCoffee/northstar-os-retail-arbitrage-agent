import { Navigate } from 'react-router-dom'
import { useSession, hasPerm } from '../foundation/session.jsx'

export default function RouteGuard({ permission, children }) {
  const session = useSession()
  if (!session.authenticated) return <Navigate to="/sign-in" replace />
  if (permission && !hasPerm(session, permission)) return <Navigate to="/home" replace />
  return children
}