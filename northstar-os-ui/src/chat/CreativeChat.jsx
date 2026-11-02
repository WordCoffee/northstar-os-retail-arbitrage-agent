// Creative Studio's Northstar surface (S1) — now a thin wrapper over the
// universal ChatSurface (V3) with the "create" focus. The studio's simple
// branch (CreativeStudio.jsx) renders this component unchanged.
import { useNavigate } from 'react-router-dom'
import ChatSurface from './ChatSurface.jsx'
import { useMode } from '../context/ModeContext.jsx'
import { useShell } from '../shell/ShellContext.jsx'

const FALLBACK_CREATE = {
  id: 'create',
  label: 'Create',
  blurb: 'Packaging, product photos, listing images, ad creative.',
  suggestions: [
    'Draft three directions for a Lion\u2019s Mane pouch \u2014 kraft, botanical, premium shelf.',
    'Build a stand-up pouch dieline for a 6 oz powder.',
    'Give me a shot list for a warm-linen product photo of a stand-up pouch.',
  ],
}

export default function CreativeChat() {
  const shell = useShell()
  const { advancedAllowed, setMode } = useMode()
  const navigate = useNavigate()
  const focus = (shell.focuses || []).find((f) => f.id === 'create') || FALLBACK_CREATE
  const openAdvanced = advancedAllowed
    ? (path) => { setMode('advanced'); navigate(path || '/design-studio') }
    : null
  return (
    <ChatSurface
      focus={focus}
      heading="Creative Studio"
      sub="Master Brain chat"
      onOpenAdvanced={openAdvanced}
    />
  )
}
