import {
  BarChart3,
  BookOpen,
  Camera,
  FileImage,
  HelpCircle,
  Leaf,
  Menu,
  NotebookPen,
  X,
} from 'lucide-react'
import { useState, type ReactNode } from 'react'
import type { View } from '../types'
import { BrandMark } from './icons'

const primaryNav: Array<{ id: View; label: string; icon: typeof Camera }> = [
  { id: 'diagnose', label: 'Diagnose', icon: Camera },
  { id: 'issues', label: 'Issue library', icon: BookOpen },
  { id: 'log', label: 'Grow log', icon: NotebookPen },
]

const moreNav: Array<{ id: View; label: string; icon: typeof Camera }> = [
  { id: 'references', label: 'Reference images', icon: FileImage },
  { id: 'atlas', label: 'Plant atlas', icon: Leaf },
  { id: 'about', label: 'About Grow Doc', icon: HelpCircle },
]

interface AppShellProps {
  activeView: View
  onViewChange: (view: View) => void
  children: ReactNode
}

export function AppShell({ activeView, onViewChange, children }: AppShellProps) {
  const [menuOpen, setMenuOpen] = useState(false)

  const chooseView = (view: View) => {
    onViewChange(view)
    setMenuOpen(false)
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }

  return (
    <div className="app-shell">
      <header className="site-header">
        <a className="brand" href="https://dtfseeds.com/" aria-label="DTF Genetics home">
          <BrandMark className="brand-mark" />
          <span><strong>THC Grow Doc</strong><small>Plant diagnostics by DTF Genetics</small></span>
        </a>

        <nav className="desktop-nav" aria-label="Grow Doc navigation">
          {primaryNav.map((item) => (
            <button key={item.id} className={activeView === item.id ? 'active' : ''} onClick={() => chooseView(item.id)}>{item.label}</button>
          ))}
        </nav>

        <div className="header-actions">
          <button className="reference-button" onClick={() => chooseView('references')}><FileImage size={17} /> References</button>
          <button className="menu-button" onClick={() => setMenuOpen((current) => !current)} aria-label={menuOpen ? 'Close menu' : 'Open menu'} aria-expanded={menuOpen}>
            {menuOpen ? <X /> : <Menu />}
          </button>
        </div>
      </header>

      {menuOpen ? (
        <nav className="mobile-nav" aria-label="Grow Doc mobile navigation">
          {[...primaryNav, ...moreNav].map((item) => {
            const Icon = item.icon
            return <button key={item.id} className={activeView === item.id ? 'active' : ''} onClick={() => chooseView(item.id)}><Icon size={19} />{item.label}</button>
          })}
        </nav>
      ) : null}

      <main>{children}</main>
      <footer>
        <div><BrandMark className="footer-mark" /><strong>THC Grow Doc</strong></div>
        <p>Photo-first plant-health screening with source-backed guidance and clear limits.</p>
        <div className="footer-links">
          <button onClick={() => chooseView('about')}>How Grow Doc works</button>
          <button onClick={() => chooseView('coverage')}><BarChart3 size={15} /> Research coverage</button>
        </div>
        <span>Teaching Healthy Cultivation · DTF Genetics</span>
      </footer>
    </div>
  )
}
