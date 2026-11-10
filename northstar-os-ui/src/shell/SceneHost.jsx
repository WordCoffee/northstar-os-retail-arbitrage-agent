// THE SHELL'S SCENE POINT.
//
// Mounted exactly once, by `ShellLayout`, as the first child of the app frame.
// It answers one question — which scene does the active workspace own? — and
// hands that to `SceneSurface`, which owns the single canvas.
//
// Why the shell and not the page: `WorkspacePanels` keeps a page mounted per
// open tab, so a per-page canvas would mean N canvases and N animation loops,
// and a hidden tab would keep painting. One bed, re-pointed at the active
// service, is the only shape that satisfies "one scene loaded per service".
//
// `serviceId` is the active tab id when the location is a workspace; otherwise
// the path picks the scene (`sceneServiceIdForPath`), falling back to the home
// scene for /home, admin and the customer rooms.

import SceneSurface from '../scenes/SceneSurface.jsx'
import { sceneServiceIdForPath } from '../scenes/sceneRegistry.js'

export default function SceneHost({
  serviceId = null,
  pathname = '',
  environment = null,
  onModeChange = null,
}) {
  const active = serviceId || sceneServiceIdForPath(pathname || '/')
  return (
    <SceneSurface
      serviceId={active}
      environment={environment}
      onModeChange={onModeChange}
    />
  )
}
