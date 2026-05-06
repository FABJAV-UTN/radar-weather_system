import { useState } from 'react'
import Dashboard from './views/Dashboard.jsx'
import ImagesTable from './views/ImagesTable.jsx'
import SchedulerStatus from './views/SchedulerStatus.jsx'

const NAV = [
  { id: 'dashboard', label: 'Dashboard' },
  { id: 'images', label: 'Imágenes' },
  { id: 'scheduler', label: 'Scheduler DACC' },
]

export default function App() {
  const [view, setView] = useState('dashboard')

  return (
    <div style={{ minHeight: '100vh', display: 'flex', flexDirection: 'column' }}>
      <header style={{
        borderBottom: '1px solid var(--border)',
        padding: '0 2rem',
        display: 'flex',
        alignItems: 'center',
        gap: '2rem',
        height: '52px',
        position: 'sticky',
        top: 0,
        background: 'var(--bg)',
        zIndex: 10,
      }}>
        <div style={{ display: 'flex', alignItems: 'baseline', gap: '8px' }}>
          <span style={{ fontSize: '14px', fontWeight: 700, letterSpacing: '0.05em', color: 'var(--accent)' }}>RADAR</span>
          <span style={{ fontSize: '11px', color: 'var(--text-muted)', letterSpacing: '0.08em' }}>SAN RAFAEL · MDZ</span>
        </div>
        <nav style={{ display: 'flex', gap: '0' }}>
          {NAV.map(n => (
            <button
              key={n.id}
              onClick={() => setView(n.id)}
              style={{
                border: 'none',
                borderBottom: view === n.id ? '2px solid var(--accent)' : '2px solid transparent',
                borderRadius: 0,
                padding: '0 16px',
                height: '52px',
                color: view === n.id ? 'var(--accent)' : 'var(--text-secondary)',
                background: 'transparent',
                fontSize: '12px',
                letterSpacing: '0.04em',
              }}
            >
              {n.label.toUpperCase()}
            </button>
          ))}
        </nav>
      </header>

      <main style={{ flex: 1, padding: '2rem', maxWidth: '1200px', margin: '0 auto', width: '100%' }}>
        {view === 'dashboard' && <Dashboard />}
        {view === 'images' && <ImagesTable />}
        {view === 'scheduler' && <SchedulerStatus />}
      </main>
    </div>
  )
}