import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import App from './App'
import './styles.css'
import './visual-observations.css'
import './growdoc-visual-polish.css'
import './growdoc-visual-polish-views.css'
import './growdoc-mobile-containment.css'
import './growdoc-visual-system-v3.css'
import './growdoc-secondary-views-v3.css'
import './growdoc-shell-v3.css'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
