import {
  BarChart3,
  BookOpen,
  Camera,
  Database,
  FileImage,
  HelpCircle,
  Menu,
  NotebookPen,
  X,
  ExternalLink,
  Gamepad,
} from 'lucide-react'
import { useState, type ReactNode } from 'react'
import type { View } from '../types'
import { BrandMark } from './icons'

const navItems: Array<{ id: View; label: string; icon: typeof Camera }> = [
  { id: 'diagnose', label: 'Diagnose', icon: Camera },
  { id: 'issues', label: 'Issue library', icon: BookOpen },
  { id: 'references', label: 'Reference images', icon: FileImage },
  { id: 'log', label: 'Grow log', icon: NotebookPen },
  { id: 'coverage', label: 'Dataset coverage', icon: BarChart3 },
  { id: 'games', label: 'Game hub', icon: Gamepad },
  { id: 'about', label: 'About', icon: HelpCircle },
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
          <span><strong>THC Grow Doc</strong><small>by DTF Genetics</small></span>
        </a>
        <nav className="desktop-nav" aria-label="Grow Doc navigation">
          {navItems.slice(0, 4).map((item) => (
            <button key={item.id} className={activeView === item.id ? 'active' : ''} onClick={() => chooseView(item.id)}>{item.label}</button>
          ))}
        </nav>
        <div className="header-actions">
          <button className="dataset-button" onClick={() => chooseView('coverage')}><Database size={17} /> Dataset v0.2</button>
          <a className="external-app-button" href="https://canna-ph-flow.base44.app" target="_blank" rel="noopener noreferrer" title="Open Canna pH Flow app in new tab"><ExternalLink size={14} /> Open Canna pH Flow</a>
          <button className="menu-button" onClick={() => setMenuOpen((current) => !current)} aria-label={menuOpen ? 'Close menu' : 'Open menu'} aria-expanded={menuOpen}>
            {menuOpen ? <X /> : <Menu />}
          </button>
        </div>
      </header>

      {menuOpen ? (
        <nav className="mobile-nav" aria-label="Grow Doc mobile navigation">
          <a className="external-app-button" href="https://canna-ph-flow.base44.app" target="_blank" rel="noopener noreferrer" title="Open Canna pH Flow app in new tab"><ExternalLink size={14} /> Open Canna pH Flow</a>
          {navItems.map((item) => {
            const Icon = item.icon
            return <button key={item.id} className={activeView === item.id ? 'active' : ''} onClick={() => chooseView(item.id)}><Icon size={19} />{item.label}</button>
          })}
        </nav>
      ) : null}

      <main>{children}</main>
      <footer>
        <div><BrandMark className="footer-mark" /><strong>THC Grow Doc</strong></div>
        <p>Evidence-guided screening, not a laboratory diagnosis. Follow local laws and product labels.</p>
        <span>App 0.2.0 · Dataset 0.2.0 · Schema 1.0</span>
      </footer>
    </div>
  )
}
