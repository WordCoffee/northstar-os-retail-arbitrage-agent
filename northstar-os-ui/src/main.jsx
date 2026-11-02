import { createElement } from 'react'
import { createRoot } from 'react-dom/client'
import App from './App.jsx'
import './styles/tokens.css'
import './styles/app.css'
import './styles/studio.css'
import './foundation/foundation.css'
import './styles/chat.css'
import './styles/shell.css'
import './styles/simple.css'   // V4.2 Simple-mode rebuild — must load last
import './styles/simple-designs.css' // Ten Simple-mode compositions, after simple.css
import './styles/celestial.css' // §11B.2 celestial backdrop — after simple.css
import './styles/galactic.css'  // Galactic plate + obsidian surfaces — after celestial
import './styles/baroque.css'   // "The Gilded Void" Baroque theme — after celestial
import './styles/workbench.css' // U3 workbench shell — last, scoped to .wb-*

const root = createRoot(document.getElementById('root'))
root.render(createElement(App))