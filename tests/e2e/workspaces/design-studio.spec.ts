// block3-workspaces — core six, role "design" (Design Studio).
// The assertions live in `_runner.ts`; this file only names the service, so the
// test reads the same `ty/northstar_workspaces.json` the UI renders from.
import { runCoreWorkspace } from './_runner'

runCoreWorkspace('design-studio')
