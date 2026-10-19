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

const root = createRoot(document.getElementById('root'))
root.render(createElement(App))