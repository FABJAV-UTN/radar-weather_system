const BASE = ''

export async function getStats() {
  const r = await fetch(BASE + '/api/v1/images/stats')
  if (!r.ok) throw new Error('stats ' + r.status)
  return r.json()
}

export async function getImages({ limit = 20, offset = 0, dateFrom, dateTo } = {}) {
  let url = BASE + `/api/v1/images?limit=${limit}&offset=${offset}`
  if (dateFrom) url += '&date_from=' + encodeURIComponent(dateFrom)
  if (dateTo) url += '&date_to=' + encodeURIComponent(dateTo)
  const r = await fetch(url)
  if (!r.ok) throw new Error('images ' + r.status)
  return r.json()
}

export async function getSchedulerStatus() {
  const r = await fetch(BASE + '/api/v1/radar/process-dacc/status')
  if (!r.ok) throw new Error('scheduler ' + r.status)
  return r.json()
}

export async function startScheduler() {
  const r = await fetch(BASE + '/api/v1/radar/process-dacc', { method: 'POST' })
  if (!r.ok) throw new Error('start ' + r.status)
  return r.json()
}

export async function stopScheduler() {
  const r = await fetch(BASE + '/api/v1/radar/process-dacc/stop', { method: 'POST' })
  if (!r.ok) throw new Error('stop ' + r.status)
  return r.json()
}