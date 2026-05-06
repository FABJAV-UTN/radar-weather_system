import { useEffect, useState } from 'react'
import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts'
import { getStats, getImages } from '../api.js'

function StatCard({ label, value, accent }) {
  return (
    <div style={{
      background: 'var(--bg-card)',
      border: '1px solid var(--border)',
      borderRadius: 'var(--radius-lg)',
      padding: '1.25rem 1.5rem',
      borderLeft: accent ? `3px solid ${accent}` : undefined,
    }}>
      <p style={{ fontSize: '11px', color: 'var(--text-muted)', letterSpacing: '0.08em', marginBottom: '8px' }}>
        {label.toUpperCase()}
      </p>
      <p style={{ fontSize: '22px', fontWeight: 700, color: 'var(--text-primary)', letterSpacing: '-0.02em' }}>
        {value}
      </p>
    </div>
  )
}

function fmtTs(ts) {
  if (!ts) return '—'
  const d = new Date(ts)
  return d.toLocaleDateString('es-AR') + ' ' + d.toLocaleTimeString('es-AR', { hour: '2-digit', minute: '2-digit' })
}

const CustomTooltip = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null
  return (
    <div style={{
      background: 'var(--bg-card)', border: '1px solid var(--border)',
      borderRadius: 'var(--radius)', padding: '8px 12px', fontSize: '12px',
    }}>
      <p style={{ color: 'var(--text-secondary)', marginBottom: 4 }}>{label}</p>
      <p style={{ color: 'var(--accent)' }}>{payload[0].value?.toLocaleString('es-AR')} px</p>
    </div>
  )
}

export default function Dashboard() {
  const [stats, setStats] = useState(null)
  const [chartData, setChartData] = useState([])
  const [error, setError] = useState(null)

  useEffect(() => {
    getStats()
      .then(setStats)
      .catch(() => setError('No se pudo conectar con la API'))

    getImages({ limit: 100, offset: 0 })
      .then(d => {
        const data = [...d.items].reverse().map(img => ({
          time: new Date(img.image_timestamp).toLocaleTimeString('es-AR', { hour: '2-digit', minute: '2-digit' }),
          pixels: img.metadata?.storm_pixel_count ?? 0,
          dbz: img.metadata?.max_dbz ?? 0,
        }))
        setChartData(data)
      })
      .catch(() => {})
  }, [])

  if (error) return (
    <div style={{ color: 'var(--danger)', padding: '2rem', border: '1px solid var(--danger)', borderRadius: 'var(--radius-lg)' }}>
      {error} — verificá que la API esté corriendo en el puerto 8000.
    </div>
  )

  return (
    <div>
      <div style={{ marginBottom: '2rem' }}>
        <h1 style={{ fontSize: '18px', fontWeight: 500, letterSpacing: '0.02em', marginBottom: '4px' }}>
          Dashboard
        </h1>
        <p style={{ color: 'var(--text-muted)', fontSize: '12px' }}>
          Evento 6 de enero 2025 · banco local
        </p>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '12px', marginBottom: '2rem' }}>
        <StatCard label="Total imágenes" value={stats ? stats.total_images.toLocaleString('es-AR') : '…'} accent="var(--accent)" />
        <StatCard label="Máx. dBZ global" value={stats?.max_dbz_global != null ? Math.round(stats.max_dbz_global) + ' dBZ' : '…'} accent="var(--danger)" />
        <StatCard label="Inicio evento" value={stats?.date_range_min ? fmtTs(stats.date_range_min) : '…'} />
        <StatCard label="Fin evento" value={stats?.date_range_max ? fmtTs(stats.date_range_max) : '…'} />
      </div>

      {chartData.length > 0 && (
        <div style={{
          background: 'var(--bg-card)', border: '1px solid var(--border)',
          borderRadius: 'var(--radius-lg)', padding: '1.5rem',
        }}>
          <p style={{ fontSize: '11px', color: 'var(--text-muted)', letterSpacing: '0.08em', marginBottom: '1.5rem' }}>
            PÍXELES DE TORMENTA EN EL TIEMPO
          </p>
          <ResponsiveContainer width="100%" height={220}>
            <AreaChart data={chartData} margin={{ top: 0, right: 0, left: 0, bottom: 0 }}>
              <defs>
                <linearGradient id="grad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#4f8ef7" stopOpacity={0.3} />
                  <stop offset="95%" stopColor="#4f8ef7" stopOpacity={0} />
                </linearGradient>
              </defs>
              <XAxis dataKey="time" tick={{ fontSize: 10, fill: '#555972' }} interval="preserveStartEnd" axisLine={false} tickLine={false} />
              <YAxis tick={{ fontSize: 10, fill: '#555972' }} axisLine={false} tickLine={false} tickFormatter={v => (v/1000).toFixed(0) + 'k'} />
              <Tooltip content={<CustomTooltip />} />
              <Area type="monotone" dataKey="pixels" stroke="#4f8ef7" strokeWidth={1.5} fill="url(#grad)" dot={false} />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      )}
    </div>
  )
}