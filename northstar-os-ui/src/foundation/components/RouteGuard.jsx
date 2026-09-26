// Route guard — role/permission-aware rendering.
import { useSession, hasPerm } from '../session.jsx'
import { StateMessage } from './StatusPrimitives.jsx'

export default function RouteGuard({ permission, children }) {
  const session = useSession()
  if (!permission) return children
  if (!hasPerm(session, permission)) {
    return (
      <div className="page">
        <div className="card">
          <StateMessage state="denied"
                        title="You don’t have access to this area"
                        detail={`Requires permission: ${permission}. Current role: ${session.role || 'none'}.`} />
        </div>
      </div>
    )
  }
  return children
}