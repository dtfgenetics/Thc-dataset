import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import App from './App'
import './styles.css'
import './visual-observations.css'
import './growdoc-visual-polish.css'
import './growdoc-visual-polish-views.css'
import './growdoc-mobile-containment.css'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
