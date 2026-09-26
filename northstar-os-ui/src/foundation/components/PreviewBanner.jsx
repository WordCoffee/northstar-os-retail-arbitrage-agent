// Persistent, non-dismissable customer-preview banner (owner decision 5).
import { useSession } from '../session.jsx'

export default function PreviewBanner() {
  const { isPreview, preview, endPreview } = useSession()
  if (!isPreview) return null
  return (
    <div className="fs-preview-banner" role="alert">
      <span className="fs-preview-dot" aria-hidden="true" />
      <strong>Previewing as customer</strong>
      <span className="fs-preview-ctx">
        org {preview?.target_organization_id}
        {preview?.target_role ? ` · role ${preview.target_role}` : ''}
        {preview?.reason ? ` · ${preview.reason}` : ''}
      </span>
      <span className="fs-preview-ro">READ-ONLY</span>
      <button className="btn" onClick={endPreview}>Exit preview</button>
    </div>
  )
}