import { ExternalLink, Gamepad } from 'lucide-react'

export default function GamesHub() {
  const games = [
    {
      id: 'canna-ph-flow',
      title: 'Canna pH Flow',
      url: 'https://canna-ph-flow.base44.app',
      img: 'https://canna-ph-flow.base44.app/favicon.ico',
      description: 'Interactive pH guidance and flow for cannabis cultivation.',
    },
    {
      id: 'inescapable-grow-smart-lab',
      title: 'Inescapable Grow Smart Lab',
      url: 'https://inescapable-grow-smart-lab.base44.app',
      img: 'https://inescapable-grow-smart-lab.base44.app/favicon.ico',
      description: 'Experimental grow-lab dashboard and interactive learning tool.',
    },
  ]

  return (
    <div className="view-container games-view">
      <div className="view-intro"><div><span>Interactive tools</span><h1>Game Hub & Tools</h1><p>External interactive tools and demos useful for growers and researchers. These open in a new tab.</p></div></div>
      <section className="games-grid">
        {games.map((g) => (
          <a key={g.id} className="game-tile" href={g.url} target="_blank" rel="noopener noreferrer">
            <div className="tile-media">
              <img src={g.img} alt={`${g.title} icon`} onError={(e) => { (e.target as HTMLImageElement).style.display = 'none' }} />
            </div>
            <div className="tile-body">
              <h3>{g.title} <ExternalLink size={14} /></h3>
              <p>{g.description}</p>
            </div>
          </a>
        ))}
      </section>
    </div>
  )
}
