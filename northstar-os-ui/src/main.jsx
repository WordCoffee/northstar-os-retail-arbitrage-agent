import { createElement } from 'react'
import { createRoot } from 'react-dom/client'
import App from './App.jsx'
// Fonts are imported through the bundler, not linked from public/. Linking
// `/ui/fonts/fonts.css` produced `/ui/ui/fonts/fonts.css` under the dev server's
// base and WebKit refused it as a non-CSS MIME type, so the serif never loaded
// on an iPhone (measured 2026-11-06). Importing lets Vite own the URL.
import './styles/fonts.css'
import './styles/tokens.css'
import './styles/app.css'
import './styles/studio.css'
import './foundation/foundation.css'
import './styles/chat.css'
import './styles/shell.css'
import './styles/simple.css'   // V4.2 Simple-mode rebuild - must load last
import './styles/simple-designs.css' // Ten Simple-mode compositions, after simple.css
// Canonical overrides for the empty state and the status row: simple.css and
// simple-designs.css define the same selectors more than once, so the winner
// depended on source order. Loading this after both makes one block the source
// of truth. See the header comment in canonical.css.
import './styles/canonical.css'
import './styles/celestial.css' // §11B.2 celestial backdrop — after simple.css
import './styles/galactic.css'  // Galactic plate + obsidian surfaces — after celestial
import './styles/baroque.css'   // "The Gilded Void" Baroque theme — after celestial
import './styles/workbench.css' // U3 workbench shell — last, scoped to .wb-*
import './styles/kit.css'      // U4 glass kit — reads the theme variables
import './styles/canvas.css'   // U7 studio canvas workspace — after the kit

const root = createRoot(document.getElementById('root'))
root.render(createElement(App))