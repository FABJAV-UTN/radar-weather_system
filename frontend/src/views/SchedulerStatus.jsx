import { useEffect, useState } from 'react'
import { getSchedulerStatus, startScheduler, stopScheduler } from '../api.js'

function fmtTs(ts) {
  if (!ts) return '—'
  return new Date(ts).toLocaleString('es-AR')
}

export default function SchedulerStatus() {
  const [status, setStatus] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [actionMsg, setActionMsg] = useState(null)

  const load = () => {
    getSchedulerStatus()
      .then(setStatus)
      .catch(() => setError('No se pudo obtener el estado del scheduler'))
  }

  useEffect(() => {
    load()
    const interval = setInterval(load, 5000)
    return () => clearInterval(interval)
  }, [])

  const handleStart = async () => {
    setLoading(true); setActionMsg(null)
    try { await startScheduler(); setActionMsg('Scheduler iniciado'); load() }
    catch (e) { setActionMsg('Error: ' + e.message) }
    finally { setLoading(false) }
  }

  const handleStop = async () => {
    setLoading(true); setActionMsg(null)
    try { await stopScheduler(); setActionMsg('Scheduler detenido'); load() }
    catch (e) { setActionMsg('Error: ' + e.message) }
    finally { setLoading(false) }
  }

  const isRunning = status?.is_running

  return (
    <div>
      <div style={{ marginBottom: '1.5rem' }}>
        <h1 style={{ fontSize: '18px', fontWeight: 500, marginBottom: '4px' }}>Scheduler DACC</h1>
        <p style={{ color: 'var(--text-muted)', fontSize: '12px' }}>
          Loop de descarga automática desde contingencias.mendoza.gov.ar
        </p>
      </div>

      {error && (
        <div style={{ color: 'var(--danger)', padding: '1rem', border: '1px solid var(--danger)', borderRadius: 'var(--radius)', marginBottom: '1.5rem' }}>
          {error}
        </div>
      )}

      <div style={{ display: 'flex', alignItems: 'center', gap: '16px', marginBottom: '2rem' }}>
        <div style={{
          display: 'flex', alignItems: 'center', gap: '8px',
          padding: '8px 16px',
          background: 'var(--bg-card)', border: '1px solid var(--border)',
          borderRadius: 'var(--radius-lg)',
        }}>
          <div style={{
            width: '8px', height: '8px', borderRadius: '50%',
            background: isRunning ? 'var(--success)' : 'var(--text-muted)',
            boxShadow: isRunning ? '0 0 6px var(--success)' : 'none',
            transition: 'all 0.3s',
          }} />
          <span style={{ fontSize: '12px', letterSpacing: '0.06em', color: isRunning ? 'var(--success)' : 'var(--text-muted)' }}>
            {status == null ? 'CARGANDO' : isRunning ? 'ACTIVO' : 'DETENIDO'}
          </span>
        </div>

        <button onClick={handleStart} disabled={loading || isRunning}>▶ Iniciar</button>
        <button onClick={handleStop} disabled={loading || !isRunning}>■ Detener</button>
        <button onClick={load} disabled={loading}>↻ Actualizar</button>
      </div>

      {actionMsg && (
        <div style={{ padding: '10px 14px', background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: 'var(--radius)', marginBottom: '1.5rem', fontSize: '12px', color: 'var(--text-secondary)' }}>
          {actionMsg}
        </div>
      )}

      {status && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '12px' }}>
          {[
            { label: 'Iniciado en', value: fmtTs(status.started_at) },
            { label: 'Última descarga', value: fmtTs(status.last_download_at) },
            { label: 'Último timestamp imagen', value: fmtTs(status.last_image_timestamp) },
            { label: 'Procesadas esta sesión', value: status.total_processed_this_session },
            { label: 'Duplicadas saltadas', value: status.total_skipped_duplicates },
            { label: 'Descartadas inválidas', value: status.total_discarded_invalid },
            { label: 'Próxima ejecución en', value: status.next_run_in_seconds > 0 ? status.next_run_in_seconds + 's' : '—' },
          ].map(item => (
            <div key={item.label} style={{
              background: 'var(--bg-card)', border: '1px solid var(--border)',
              borderRadius: 'var(--radius-lg)', padding: '1rem 1.25rem',
            }}>
              <p style={{ fontSize: '11px', color: 'var(--text-muted)', letterSpacing: '0.06em', marginBottom: '6px' }}>
                {item.label.toUpperCase()}
              </p>
              <p style={{ fontSize: '15px', fontWeight: 600, color: 'var(--text-primary)' }}>
                {item.value ?? '—'}
              </p>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}