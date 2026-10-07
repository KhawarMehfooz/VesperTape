import { useEffect, useRef, useState } from 'react'
import type { ErrorResponse, PlaylistSelection, PreviewResponse, JobResponse, JobsResponse } from './api/contracts'

export default function App() {
  const [jobs, setJobs] = useState<JobResponse[]>([])
  const [feedError, setFeedError] = useState(false)
  useEffect(() => {
    const feed = new EventSource('/api/jobs/events')
    feed.addEventListener('jobs', event => {
      setJobs((JSON.parse((event as MessageEvent).data) as JobsResponse).jobs)
      setFeedError(false)
    })
    feed.onerror = () => setFeedError(true)
    return () => feed.close()
  }, [])
  const [url, setUrl] = useState('')
  const [preview, setPreview] = useState<PreviewResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [mode, setMode] = useState('all')
  const [start, setStart] = useState(1)
  const [end, setEnd] = useState(1)
  const requestId = useRef(0)
  const abort = useRef<AbortController | null>(null)
  const indices = preview?.items.map(item => item.playlist_index).filter((index): index is number => index !== null) ?? []
  const selection: PlaylistSelection = { item_indices: mode === 'all' ? [] : mode === 'one' ? [start] : indices.filter(index => index >= start && index <= end) }
  const validSelection = mode === 'all' || (indices.includes(start) && (mode === 'one' || (end >= start && indices.includes(end))))

  function reset() {
    requestId.current += 1
    abort.current?.abort()
    setPreview(null)
    setError('')
    setLoading(false)
  }

  async function inspect(event: React.FormEvent) {
    event.preventDefault()
    reset()
    const id = requestId.current
    const controller = new AbortController()
    abort.current = controller
    setLoading(true)
    try {
      const response = await fetch('/api/preview', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url }), signal: controller.signal,
      })
      const data: PreviewResponse | ErrorResponse = await response.json()
      if (id !== requestId.current) return
      if (!response.ok || 'error' in data) {
        setError('error' in data ? data.error.message : 'Could not inspect this link.')
        return
      }
      setPreview(data)
      setMode('all')
      setStart(data.items[0]?.playlist_index ?? 1)
      setEnd(data.items.at(-1)?.playlist_index ?? 1)
    } catch {
      if (id === requestId.current) setError('Could not reach the preview service. Please try again.')
    } finally {
      if (id === requestId.current) setLoading(false)
    }
  }

  return (
    <main className="shell">
      <header className="topbar"><span className="wordmark"><span className="mark">◉</span> VESPERTAPE</span><span className="edition">LINK INSPECTOR</span></header>
      <section className="intro"><div className="kicker">YOUR MEDIA, READY TO GO</div><h1>Inspect a link.</h1><p>Preview a video or playlist before adding it to your downloads.</p></section>
      <section className="window" aria-label="Link preview">
        <div className="titlebar">VESPERTAPE / PREVIEW</div>
        <div className="well">
          <h2>Source link</h2><p>Paste a public video or playlist URL.</p>
          <form className="link-row" onSubmit={inspect}>
            <label htmlFor="source-url">URL</label>
            <input id="source-url" type="url" required value={url} placeholder="https://…" onChange={event => { reset(); setUrl(event.target.value) }} />
            <button disabled={loading || !url.trim()}>{loading ? 'Inspecting…' : 'Preview'}</button>
          </form>
          <div className="note">Metadata only. Previewing does not download media.</div>
        </div>
        {loading && <p className="preview-message" role="status">Inspecting media and available formats…</p>}
        {error && <p className="preview-message error" role="alert">{error}</p>}
        {preview && <div className="well" aria-live="polite">
          <h2>{preview.title}</h2>
          {preview.kind === 'playlist' && <>
            <p>{preview.total_items ?? preview.items.length} playlist items. Showing up to 100 items.</p>
            <fieldset className="selection"><legend>Playlist selection</legend>
              <label>Download <select value={mode} onChange={event => setMode(event.target.value)}><option value="all">Full playlist</option><option value="one">One item</option><option value="range">Range</option></select></label>
              {mode !== 'all' && <label>{mode === 'one' ? 'Item' : 'From'}<input type="number" min="1" value={start} onChange={event => setStart(Number(event.target.value))} /></label>}
              {mode === 'range' && <label>To<input type="number" min={start} value={end} onChange={event => setEnd(Number(event.target.value))} /></label>}
            </fieldset>
            {!validSelection && <p role="alert">Choose indexes from the preview, with the end at or after the start.</p>}
            {validSelection && <p>Selection: {selection.item_indices.length ? selection.item_indices.join(', ') : 'full playlist'}</p>}
          </>}
          {!preview.items.length && <p role="status">No playable items were found in this playlist.</p>}
          <div className="preview-items">{preview.items.filter(item => mode === 'all' || selection.item_indices.includes(item.playlist_index ?? 1)).map(item => <article className="media-item" key={`${item.playlist_index}-${item.id}`}>
            {item.thumbnail_url && <img src={item.thumbnail_url} alt="" loading="lazy" referrerPolicy="no-referrer" />}
            <div><h3>{item.playlist_index ? `${item.playlist_index}. ` : ''}{item.title}</h3><p>{item.uploader ?? 'Unknown uploader'} · {item.duration_seconds === null ? 'Duration unavailable' : `${Math.floor(item.duration_seconds / 60)}:${String(Math.floor(item.duration_seconds % 60)).padStart(2, '0')}`}</p>
              {item.formats.length ? <details><summary>{item.formats.length} available formats</summary><ul>{item.formats.map(format => <li key={format.id}>{format.id} · {format.extension} · {format.height ? `${format.height}p` : format.video_codec === 'none' ? 'Audio' : 'Media'}{format.filesize_bytes !== null ? ` · ${(format.filesize_bytes / 1048576).toFixed(1)} MB` : ''}</li>)}</ul></details> : <p role="status">No downloadable formats are available for this item.</p>}
            </div>
          </article>)}</div>
          <div className="note">Download submission controls are coming next. Queued jobs appear below.</div>
        </div>}
      </section>
      <section className="window" aria-label="Download queue">
        <div className="titlebar">VESPERTAPE / DOWNLOAD QUEUE</div>
        <div className="well">
          {feedError && <p role="status">Live updates disconnected. Reconnecting…</p>}
          {!jobs.length && <p>No downloads queued yet.</p>}
          {jobs.map(job => <article className="media-item" key={job.id}>
            <div><h3>{job.title ?? 'New download'}</h3><p>{job.status} · {job.output_name ?? 'Output pending'}</p>
              {job.status === 'downloading' && <><progress max="100" value={job.progress.percent ?? undefined} aria-label="Download progress" /><p>
                {job.progress.percent === null ? 'Size unknown' : `${job.progress.percent.toFixed(1)}%`}
                {job.progress.speed_bytes_per_second !== null && ` · ${(job.progress.speed_bytes_per_second / 1048576).toFixed(2)} MB/s`}
                {job.progress.eta_seconds !== null && ` · ${Math.ceil(job.progress.eta_seconds)}s remaining`}
              </p></>}
              {job.error && <p className="error">{job.error.message}</p>}
            </div>
          </article>)}
        </div>
      </section>
    </main>
  )
}
