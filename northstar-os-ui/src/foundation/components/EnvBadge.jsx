// Environment indicator (sandbox | production) — one of three orthogonal dimensions.
import { useSession } from '../session.jsx'

export default function EnvBadge() {
  const { environment, viewContext } = useSession()
  const sandbox = environment === 'sandbox'
  return (
    <span className={`fs-env ${sandbox ? 'fs-env-sandbox' : 'fs-env-prod'}`}
          title={`environment: ${environment}`}>
      {sandbox ? 'SANDBOX' : 'PRODUCTION'}
      {viewContext === 'audited_customer_preview' && ' · PREVIEW'}
    </span>
  )
}