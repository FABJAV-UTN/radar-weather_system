import { useEffect, useState } from 'react'
import { getImages } from '../api.js'

const LIMIT = 25

function dbzColor(val) {
  if (!val) return 'var(--text-muted)'
  if (val >= 75) return 'var(--danger)'
  if (val >= 60) return 'var(--warning)'
  if (val >= 45) return '#c8a020'
  return 'var(--success)'
}

function fmtTs(ts) {
  if (!ts) return '—'
  const d = new Date(ts)
  return d.toLocaleDateString('es-AR') + ' ' + d.toLocaleTimeString('es-AR', { hour: '2-digit', minute: '2-digit' })
}

export default function ImagesTable() {
  const [data, setData] = useState(null)
  const [offset, setOffset] = useState(0)
  const [filterFrom, setFilterFrom] = useState('')
  const [filterTo, setFilterTo] = useState('')
  const [pendingFrom, setPendingFrom] = useState('')
  const [pendingTo, setPendingTo] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  const load = (off, from, to) => {
    setLoading(true)
    setError(null)
    getImages({ limit: LIMIT, offset: off, dateFrom: from || undefined, dateTo: to || undefined })
      .then(d => {
        // Garantizar ordenamiento descendente por timestamp (más reciente primero)
        if (d?.items) {
          d.items.sort((a, b) => {
            const aTime = a.image_timestamp ? new Date(a.image_timestamp).getTime() : 0
            const bTime = b.image_timestamp ? new Date(b.image_timestamp).getTime() : 0
            return bTime - aTime  // Descendente
          })
        }
        setData(d)
        setLoading(false)
      })
      .catch(() => { setError('Error conectando con la API'); setLoading(false) })
  }

  useEffect(() => { load(0, '', '') }, [])

  const applyFilters = () => {
    setFilterFrom(pendingFrom)
    setFilterTo(pendingTo)
    setOffset(0)
    load(0, pendingFrom, pendingTo)
  }

  const clearFilters = () => {
    setPendingFrom(''); setPendingTo('')
    setFilterFrom(''); setFilterTo('')
    setOffset(0)
    load(0, '', '')
  }

  const prev = () => { const o = Math.max(0, offset - LIMIT); setOffset(o); load(o, filterFrom, filterTo) }
  const next = () => { const o = offset + LIMIT; setOffset(o); load(o, filterFrom, filterTo) }

  const total = data?.total ?? 0
  const page = Math.floor(offset / LIMIT) + 1
  const totalPages = Math.max(1, Math.ceil(total / LIMIT))

  return (
    <div>
      <div style={{ marginBottom: '1.5rem' }}>
        <h1 style={{ fontSize: '18px', fontWeight: 500, marginBottom: '4px' }}>Imágenes</h1>
        <p style={{ color: 'var(--text-muted)', fontSize: '12px' }}>
          {total > 0 ? total.toLocaleString('es-AR') + ' registros' : '…'}
        </p>
      </div>

      <div style={{ display: 'flex', gap: '10px', flexWrap: 'wrap', alignItems: 'flex-end', marginBottom: '1.25rem' }}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
          <label style={{ fontSize: '11px', color: 'var(--text-muted)', letterSpacing: '0.06em' }}>DESDE</label>
          <input type="datetime-local" value={pendingFrom} onChange={e => setPendingFrom(e.target.value)} />
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
          <label style={{ fontSize: '11px', color: 'var(--text-muted)', letterSpacing: '0.06em' }}>HASTA</label>
          <input type="datetime-local" value={pendingTo} onChange={e => setPendingTo(e.target.value)} />
        </div>
        <button onClick={applyFilters}>Buscar</button>
        {(filterFrom || filterTo) && <button onClick={clearFilters}>Limpiar</button>}
      </div>

      {error && (
        <div style={{ color: 'var(--danger)', padding: '1rem', border: '1px solid var(--danger)', borderRadius: 'var(--radius)', marginBottom: '1rem' }}>
          {error}
        </div>
      )}

      <div style={{ border: '1px solid var(--border)', borderRadius: 'var(--radius-lg)', overflow: 'hidden' }}>
        <div style={{ overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '12px' }}>
            <thead>
              <tr style={{ background: 'var(--bg-card)', borderBottom: '1px solid var(--border)' }}>
                {['ID', 'Timestamp imagen', 'Archivo', 'dBZ', 'Px tormenta', 'GeoTIFF'].map(h => (
                  <th key={h} style={{
                    padding: '10px 14px', textAlign: h === 'ID' || h === 'dBZ' || h === 'Px tormenta' ? 'right' : h === 'GeoTIFF' ? 'center' : 'left',
                    color: 'var(--text-muted)', fontWeight: 500, letterSpacing: '0.05em', whiteSpace: 'nowrap',
                  }}>{h.toUpperCase()}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {loading && (
                <tr><td colSpan={6} style={{ padding: '3rem', textAlign: 'center', color: 'var(--text-muted)' }}>cargando...</td></tr>
              )}
              {!loading && data?.items?.length === 0 && (
                <tr><td colSpan={6} style={{ padding: '3rem', textAlign: 'center', color: 'var(--text-muted)' }}>sin resultados</td></tr>
              )}
              {!loading && data?.items?.map((img, i) => (
                <tr key={img.id} style={{
                  borderBottom: '1px solid var(--border)',
                  background: i % 2 === 0 ? 'transparent' : 'rgba(255,255,255,0.015)',
                  transition: 'background 0.1s',
                }}
                  onMouseEnter={e => e.currentTarget.style.background = 'rgba(79,142,247,0.06)'}
                  onMouseLeave={e => e.currentTarget.style.background = i % 2 === 0 ? 'transparent' : 'rgba(255,255,255,0.015)'}
                >
                  <td style={{ padding: '9px 14px', textAlign: 'right', color: 'var(--text-muted)' }}>{img.id}</td>
                  <td style={{ padding: '9px 14px', fontVariantNumeric: 'tabular-nums', whiteSpace: 'nowrap' }}>{fmtTs(img.image_timestamp)}</td>
                  <td style={{ padding: '9px 14px', color: 'var(--text-secondary)', maxWidth: '240px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={img.filename}>{img.filename}</td>
                  <td style={{ padding: '9px 14px', textAlign: 'right', fontWeight: 600, color: dbzColor(img.metadata?.max_dbz) }}>
                    {img.metadata?.max_dbz ?? '—'}
                  </td>
                  <td style={{ padding: '9px 14px', textAlign: 'right', color: 'var(--text-secondary)', fontVariantNumeric: 'tabular-nums' }}>
                    {img.metadata?.storm_pixel_count?.toLocaleString('es-AR') ?? '—'}
                  </td>
                  <td style={{ padding: '9px 14px', textAlign: 'center' }}>
                    <a href={img.download_url} title="Descargar GeoTIFF" style={{ fontSize: '14px' }}>↓</a>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginTop: '1rem' }}>
        <div style={{ display: 'flex', gap: '8px' }}>
          <button onClick={prev} disabled={offset === 0}>← Anterior</button>
          <button onClick={next} disabled={offset + LIMIT >= total}>Siguiente →</button>
        </div>
        <span style={{ fontSize: '11px', color: 'var(--text-muted)', letterSpacing: '0.05em' }}>
          PÁGINA {page} / {totalPages}
        </span>
      </div>
    </div>
  )
}