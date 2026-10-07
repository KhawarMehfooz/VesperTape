import { useEffect, useRef, useState } from 'react'
import AdvancedOptions from './AdvancedOptions'
import Icon from './Icon'
import { youtubeLinkError } from './api/youtube'
import type { ErrorResponse, PlaylistSelection, PreviewResponse, JobResponse, JobsResponse, SettingsResponse, DownloadSettings, ApiError, JobActionRequest } from './api/contracts'

export default function App() {
  const [capabilities, setCapabilities] = useState<SettingsResponse | null>(null)
  const [settings, setSettings] = useState<DownloadSettings | null>(null)
  const [settingsError, setSettingsError] = useState('')
  const [settingsAttempt, setSettingsAttempt] = useState(0)
  const [submitting, setSubmitting] = useState(false)
  const submissionLock = useRef(false)
  const [submissionError, setSubmissionError] = useState<ApiError | null>(null)
  const [notice, setNotice] = useState('')
  const [destinationDraft, setDestinationDraft] = useState('default')
  const [rename, setRename] = useState(false)
  const [toast, setToast] = useState('')
  const locationDialog = useRef<HTMLDialogElement>(null)
  useEffect(() => {
    if (!toast) return
    const timer = window.setTimeout(() => setToast(''), 2500)
    return () => window.clearTimeout(timer)
  }, [toast])
  const compatibleFormats = (mode: DownloadSettings['mode'], formats: string[]) =>
    formats.filter(format => (mode === 'audio' ? ['auto', 'mp3', 'm4a', 'flac', 'wav'] : ['auto', 'mp4', 'webm']).includes(format))
  useEffect(() => {
    const controller = new AbortController()
    setSettingsError('')
    async function load() {
      try {
        const response = await fetch('/api/settings', { signal: controller.signal })
        const data: SettingsResponse | ErrorResponse = await response.json()
        if (!response.ok || 'error' in data) throw new Error('Could not load download settings.')
        const formats = compatibleFormats(data.defaults.mode, data.allowed_formats)
        setCapabilities(data)
        setSettings({ ...data.defaults, format: (formats.includes(data.defaults.format) ? data.defaults.format : formats[0] ?? 'auto') as DownloadSettings['format'] })
      } catch {
        if (!controller.signal.aborted) setSettingsError('Could not load download settings. Please retry.')
      }
    }
    void load()
    return () => controller.abort()
  }, [settingsAttempt])
  const [jobs, setJobs] = useState<JobResponse[]>([])
  const [busyJobs, setBusyJobs] = useState<Set<string>>(new Set())
  const jobLocks = useRef(new Set<string>())
  const [jobError, setJobError] = useState('')
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
  const linkError = url.trim() ? youtubeLinkError(url) : null
  const [mode, setMode] = useState('all')
  const [start, setStart] = useState(1)
  const [end, setEnd] = useState(1)
  const requestId = useRef(0)
  const abort = useRef<AbortController | null>(null)
  const indices = preview?.items.map(item => item.playlist_index).filter((index): index is number => index !== null) ?? []
  const selection: PlaylistSelection = { item_indices: mode === 'all' ? [] : mode === 'one' ? [start] : indices.filter(index => index >= start && index <= end) }
  const validSelection = mode === 'all' || (indices.includes(start) && (mode === 'one' || (end >= start && indices.includes(end))))

  const selectedItems = preview?.items.filter(item => mode === 'all' || selection.item_indices.includes(item.playlist_index ?? 1)) ?? []
  const formats = settings && capabilities ? compatibleFormats(settings.mode, capabilities.allowed_formats) : []
  const canSubmit = !linkError && !!preview && !!settings && validSelection && selectedItems.some(item => item.formats.length > 0) && formats.includes(settings.format)

  function updateSettings(patch: Partial<DownloadSettings>) {
    setSettings(current => current ? { ...current, ...patch } : current)
    setSubmissionError(null)
    setNotice('')
  }

  async function enqueue(event: React.FormEvent) {
    event.preventDefault()
    if (!canSubmit || submissionLock.current || !preview || !settings) return
    submissionLock.current = true
    setSubmitting(true)
    setSubmissionError(null)
    setNotice('')
    try {
      const response = await fetch('/api/jobs', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url: url.trim(), selection, settings: { ...settings, filename: rename ? settings.filename?.trim() || null : null } }),
      })
      const data: JobResponse | ErrorResponse = await response.json()
      if (!response.ok || !('id' in data)) {
        setSubmissionError(!('id' in data) ? data.error : { code: 'submission_failed', message: 'Could not add this download.', details: [] })
        return
      }
      const createdJob = data
      setJobs(current => current.some(job => job.id === createdJob.id) ? current : [...current, createdJob])
      setNotice('Added to downloads.')
    } catch {
      setSubmissionError({ code: 'connection_failed', message: 'Could not confirm submission. Check the queue before trying again.', details: [] })
    } finally {
      submissionLock.current = false
      setSubmitting(false)
    }
  }

  function reset() {
    requestId.current += 1
    abort.current?.abort()
    setPreview(null)
    setSubmissionError(null)
    setNotice('')
    setError('')
    setLoading(false)
  }

  async function inspect(event: React.FormEvent) {
    event.preventDefault()
    reset()
    const validationError = youtubeLinkError(url)
    if (validationError) { setError(validationError); return }
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

  const firstItem = selectedItems[0] ?? preview?.items[0]
  const activeJobs = jobs.filter(job => job.status !== 'complete' && job.status !== 'failed' && job.status !== 'canceled')
  const recentJobs = jobs.filter(job => job.status === 'complete' || job.status === 'failed' || job.status === 'canceled').sort((a, b) => b.updated_at.localeCompare(a.updated_at))
  const destinationName = settings?.destination === 'default' ? 'Downloads' : settings?.destination ?? 'Downloads'
  const duration = firstItem?.duration_seconds
  const durationLabel = duration == null ? 'Duration unavailable' : `${Math.floor(duration / 60)}:${String(Math.floor(duration % 60)).padStart(2, '0')}`

  async function controlJob(job: JobResponse, action: JobActionRequest['action'] | 'remove') {
    if (jobLocks.current.has(job.id)) return
    jobLocks.current.add(job.id)
    setBusyJobs(new Set(jobLocks.current))
    setJobError('')
    try {
      const response = await fetch(`/api/jobs/${encodeURIComponent(job.id)}${action === 'remove' ? '' : '/actions'}`, {
        method: action === 'remove' ? 'DELETE' : 'POST',
        headers: { 'Content-Type': 'application/json' },
        ...(action === 'remove' ? {} : { body: JSON.stringify({ action }) }),
      })
      if (!response.ok) {
        const data: ErrorResponse = await response.json()
        setJobError(data.error.message)
        return
      }
      // Refresh the authoritative snapshot rather than overwriting a newer SSE state.
      const snapshot = await fetch('/api/jobs')
      if (snapshot.ok) setJobs(((await snapshot.json()) as JobsResponse).jobs)
    } catch {
      setJobError('Could not confirm the download action. Check its status and try again.')
    } finally {
      jobLocks.current.delete(job.id)
      setBusyJobs(new Set(jobLocks.current))
    }
  }

  function renderJob(job: JobResponse) {
    const actions: Array<JobActionRequest['action'] | 'remove'> = job.status === 'queued' || job.status === 'downloading' ? ['pause', 'cancel'] : job.status === 'paused' ? ['resume', 'cancel'] : job.status === 'complete' ? ['remove'] : ['retry', 'remove']
    const stateClass = job.status === 'downloading' ? 'active' : job.status
    return <article className={`queue-item is-${stateClass}`} key={job.id}>
      <div className="file-icon" aria-hidden="true">{job.status === 'failed' ? '!' : job.settings.mode === 'audio' ? '♫' : '▣'}</div>
      <div><div className="queue-name">{job.title ?? 'New download'}</div>
        <div className="queue-meta">{job.settings.format.toUpperCase()} · {job.settings.quality} · {job.output_name ?? 'Output pending'}</div>
        {(job.status === 'downloading' || job.status === 'paused') && <><div className="queue-extra"><progress className="progress" max="100" value={job.progress.percent ?? undefined} aria-label="Download progress" /><span className="queue-meta">{job.progress.percent == null ? 'Size unknown' : `${job.progress.percent.toFixed(1)}%`}</span></div><div className="queue-meta">{job.progress.speed_bytes_per_second !== null && `${(job.progress.speed_bytes_per_second / 1048576).toFixed(2)} MB/s`}{job.progress.eta_seconds !== null && ` · ${Math.ceil(job.progress.eta_seconds)}s remaining`}</div></>}
        {job.status === 'complete' && <div className="completed-files">{(job.output_files ?? (job.output_name ? [job.output_name] : [])).map(filename => <a className="small-btn" key={filename} href={`/api/jobs/${encodeURIComponent(job.id)}/files/${encodeURIComponent(filename)}`} download={filename}>Save {filename}</a>)}</div>}
        {job.error && <div className="queue-meta error">{job.error.message}</div>}
      </div>
      <div className="job-controls"><div className={`queue-state is-${stateClass}`}>{job.status.toUpperCase()}</div><div className="queue-actions-inline">{actions.map(action => <button className="small-btn" key={action} disabled={busyJobs.has(job.id)} onClick={() => void controlJob(job, action)}>{action[0].toUpperCase() + action.slice(1)}</button>)}</div></div>
    </article>
  }

  return (
    <main className="shell">
      <header className="brand-header"><h1>VesperTape</h1></header>
      <section className="variant variant-a" aria-label="Classic Download Window"><div className="skin">
        <div className="titlebar"><div className="title-name"><span className="mark">✣</span> VESPERTAPE DOWNLOAD MANAGER</div><div className="window-buttons" aria-hidden="true"><i /><i /><i /></div></div>
        <div className="well">
          <h2 className="section-title">What would you like to save?</h2>
          <div className="subhead">Paste a video link and we’ll get the details ready for you.</div>
          <div style={{ height: 10 }} />
          <form className="link-row" aria-busy={loading} onSubmit={inspect}>
            <label className="field-label" htmlFor="source-url">Video link</label>
            <input className="url-input" id="source-url" disabled={submitting} type="text" inputMode="url" autoComplete="url" aria-invalid={!!linkError || !!error} aria-describedby={linkError || error ? 'link-error' : undefined} required value={url} placeholder="Paste a YouTube video or playlist link" onChange={event => { reset(); setUrl(event.target.value) }} />
            <span className="url-actions"><button className="bevel-btn" type="button" disabled={submitting} onClick={async () => {
              try {
                const value = await navigator.clipboard.readText()
                if (value) { reset(); setUrl(value); setToast('Link pasted. Take a look, then preview it.') }
                else setToast('Your clipboard looks empty.')
              } catch { setToast('Paste your video link into the box above.') }
            }}><Icon name="paste" />Paste link</button><button className="bevel-btn inspect" disabled={submitting || loading || !url.trim() || !!linkError}><Icon name="preview" />{loading ? 'Inspecting…' : 'Preview'}</button></span>
          </form>
          <div className="mini-note" aria-live="polite"><span>{loading ? 'Inspecting media and available formats…' : preview ? `${firstItem?.uploader ?? 'Source inspected'}${preview.kind === 'playlist' ? ` · ${preview.total_items ?? preview.items.length} videos detected.` : ''}` : 'Paste a YouTube video or playlist link to get started.'}</span>{preview && <span className="ready-pill"><i />Link ready</span>}</div>
          {(linkError || error) && <p id="link-error" className="preview-message error" role="alert">{linkError || error}</p>}
          {preview && <div className="preview-reveal"><div className="preview-reveal-content"><article className="source-preview">
            <div className={`preview-art${firstItem?.thumbnail_url ? ' has-image' : ''}`} aria-hidden="true">{firstItem?.thumbnail_url ? <img src={firstItem.thumbnail_url} alt="" referrerPolicy="no-referrer" /> : <span>✣</span>}</div>
            <div><div className="preview-top"><h3 className="preview-title">{preview.title}</h3><div className="preview-status"><i />{selectedItems.some(item => item.formats.length) ? 'LOOKS GOOD' : 'NO FORMATS'}</div></div><div className="preview-meta">{firstItem?.uploader ?? 'Unknown uploader'} · {durationLabel}{firstItem?.formats.some(format => format.height === 1080) && ' · 1080p available'}</div>
              {preview.kind === 'playlist' && <div className="playlist-row">
                <div className="setting-title">Playlist · {preview.total_items ?? preview.items.length} items</div>
                <select className="fake-select" aria-label="Playlist download selection" disabled={submitting} value={mode} onChange={event => { setMode(event.target.value); setSubmissionError(null); setNotice('') }}><option value="one">This video only · {start} of {preview.total_items ?? preview.items.length}</option><option value="all">Entire playlist · {preview.total_items ?? preview.items.length} videos</option><option value="range">Choose a range…</option></select>
                {mode !== 'all' && <div className="playlist-range is-visible"><span>{mode === 'one' ? 'Video' : 'Videos'}</span><input type="number" min="1" disabled={submitting} value={start} aria-label="First playlist item" onChange={event => setStart(Number(event.target.value))} />{mode === 'range' && <><span>to</span><input type="number" min={start} disabled={submitting} value={end} aria-label="Last playlist item" onChange={event => setEnd(Number(event.target.value))} /></>}<span>of {preview.total_items ?? preview.items.length}</span></div>}
                {!validSelection && <div className="error" role="alert">Choose indexes from the preview, with the end at or after the start.</div>}
              </div>}
              {!preview.items.length && <div className="preview-meta" role="status">No playable items were found in this playlist.</div>}
              {preview.items.length > 0 && !selectedItems.some(item => item.formats.length) && <div className="preview-meta error" role="status">No downloadable formats are available for this item.</div>}
            </div>
          </article></div></div>}
          <details className="source-feedback"><summary>Help · supported sources and link messages</summary><div className="feedback-list"><span className="good">✓ Link inspected</span><span className="warn">⚠ Playlist detected</span><span className="bad">! Unsupported source</span><span className="bad">! No compatible formats found</span><span className="bad">! Invalid or private link</span><span>… Inspecting source</span></div></details>
          {settingsError && <div className="preview-message error" role="alert">{settingsError} <button className="bevel-btn" type="button" onClick={() => setSettingsAttempt(value => value + 1)}>Retry settings</button></div>}
          {!settings && !settingsError && <p className="preview-message" role="status">Loading download settings…</p>}
          {settings && capabilities && <form className="config" onSubmit={enqueue} aria-busy={submitting}>
            <fieldset className="download-options" disabled={submitting}><legend className="sr-only">Download settings</legend>
              <div className="config-layout">
                <section className="mode-plate"><div className="plate-head">Save as</div><div className="mode-list">{(['audio', 'video'] as const).filter(value => capabilities.allowed_modes.includes(value)).map(value => <div className="mode" key={value}><input className={`${value}-choice`} type="radio" id={`mode-${value}`} name="download-mode" checked={settings.mode === value} onChange={() => {
                  const available = compatibleFormats(value, capabilities.allowed_formats)
                  updateSettings({ mode: value, format: (available.includes(settings.format) ? settings.format : available[0] ?? 'auto') as DownloadSettings['format'] })
                }} /><label htmlFor={`mode-${value}`}><Icon name={value} />{value === 'audio' ? 'Audio' : 'Video'}</label></div>)}</div><div className="fine-print" style={{ marginTop: 8 }}>Choose output type</div></section>
                <section className="options-plate"><div key={settings.mode} className={`format-panel ${settings.mode}-panel`}>
                  <div className="plate-head">{settings.mode === 'audio' ? 'Audio format & quality' : 'Video quality & format'}</div>
                  <div className="format-options">
                    <div className="setting"><label className="setting-title" htmlFor="quality">{settings.mode === 'audio' ? 'Audio quality' : 'Resolution'}</label>
                      {settings.mode === 'audio'
                        ? <select className="fake-select" id="quality" value="best" disabled><option value="best">Best available audio</option></select>
                        : <select className="fake-select" id="quality" value={settings.quality} onChange={event => updateSettings({ quality: event.target.value as DownloadSettings['quality'] })}>{capabilities.allowed_qualities.map(value => <option key={value} value={value}>{value === 'best' ? 'Best available · up to 4K' : value === '1080p' ? '1080p · Full HD' : value === '720p' ? '720p · Compact' : '480p · Small'}</option>)}</select>}
                    </div>
                    <div className="setting"><label className="setting-title" htmlFor="format">{settings.mode === 'audio' ? 'Audio format' : 'Container'}</label><select className="fake-select" id="format" value={formats.includes(settings.format) ? settings.format : ''} onChange={event => updateSettings({ format: event.target.value as DownloadSettings['format'] })}>{!formats.length && <option value="">No compatible formats</option>}{formats.map(value => <option key={value} value={value}>{value === 'auto' ? 'Automatic · Best compatible' : value === 'mp4' ? 'MP4 · Compatible' : value === 'webm' ? 'WebM · Open format' : value === 'm4a' ? 'M4A · AAC' : value === 'flac' ? 'FLAC · Lossless' : value.toUpperCase()}</option>)}</select></div>
                  </div>
                  {settings.mode === 'video' && <label className="check"><input type="checkbox" checked disabled />Merge best audio and video streams</label>}
                  {settings.mode === 'audio' && <div className="fine-print" style={{ marginTop: 8 }}>Uses the best available audio stream.</div>}
                  <details className="advanced"><summary>Customize {settings.mode}</summary><label className="check"><input type="checkbox" disabled />{settings.mode === 'video' ? 'Include subtitles when available' : 'Keep chapter markers'}</label><label className="check"><input type="checkbox" disabled />{settings.mode === 'video' ? 'Embed thumbnail' : 'Preserve source timestamp'}</label>{settings.mode === 'video' && <label className="check"><input type="checkbox" disabled />Prefer HDR streams</label>}<div className="setting-title" style={{ marginTop: 8 }}>Filename pattern</div><input className="fake-select" readOnly value="%(title)s.%(ext)s" aria-label="Filename pattern" /><div className="adv-note">Custom processing options are not available yet.</div></details>
                </div></section>
              </div>
              {!formats.length && <p className="preview-message error" role="alert">The server has no allowed formats for this mode. Choose another mode.</p>}
              <div className="save-options">
                <section className="save-block"><label className="save-label" htmlFor="save-path"><Icon name="folder" />Where should it go?</label><div className="path-row"><input className="url-input" id="save-path" type="text" aria-label="Save location" value={destinationName} readOnly /><button className="bevel-btn" type="button" onClick={() => { setDestinationDraft(settings.destination); locationDialog.current?.showModal() }}>Choose folder</button></div></section>
                <section className="save-block rename-setting"><div className="save-label"><Icon name="rename" />Give it a name</div><label className="check"><input className="rename-check" type="checkbox" checked={rename} onChange={event => { setRename(event.target.checked); setSubmissionError(null) }} />Choose my own file name</label><input className="url-input rename-input" type="text" aria-label="New file name" value={settings.filename ?? ''} onChange={event => updateSettings({ filename: event.target.value })} placeholder="Enter a new file name" /><div className="save-hint">Leave unchecked to keep the source title.</div></section>
              </div>
            </fieldset>
            <AdvancedOptions />
            {submissionError && <div className="submission-error" role="alert"><p>{submissionError.message}</p>{submissionError.details.length > 0 && <ul>{submissionError.details.map((detail, index) => <li key={index}>{detail.location.filter(part => part !== 'body').join(' › ')}: {detail.message}</li>)}</ul>}</div>}
            <div className="actionline"><span className="status" role="status"><i />{notice || (!preview ? 'Ready when you are' : !validSelection ? 'Choose a valid playlist selection.' : !selectedItems.some(item => item.formats.length) ? 'No downloadable formats in this selection.' : 'Ready when you are')}</span><span className="fine-print">Saved to {destinationName}</span><button className="bevel-btn primary" disabled={!canSubmit || submitting}><Icon name="download" />{submitting ? 'Adding…' : 'Add to downloads'}</button></div>
          </form>}
        </div>
        <section aria-label="Download queue"><div className="queue-head"><h2><Icon name="queue" />Your downloads</h2><span>{activeJobs.length} in progress</span></div>
          {jobError && <div className="preview-message error" role="alert">{jobError}</div>}
          {feedError && <div className="queue-note" role="status">Live updates disconnected. Reconnecting…</div>}
          <div className="download-list" aria-live="polite">{activeJobs.map(renderJob)}</div>
          {!activeJobs.length && <div className="empty-queue">No downloads queued yet.</div>}
        </section>
        <section className="history-panel" aria-label="Recent downloads"><div className="queue-head"><h2 className="history-title">Recent downloads</h2><span>{recentJobs.length} items</span></div>{recentJobs.map(renderJob)}{!recentJobs.length && <div className="empty-queue">Your saved downloads will appear here.</div>}</section>
      </div></section>
      <dialog className="location-dialog" ref={locationDialog} aria-labelledby="location-title"><form method="dialog"><div className="dialog-heading"><span className="dialog-folder">✦</span><div><h2 id="location-title">Choose a cozy spot</h2><p>Docker maps these folder names to locations you choose during setup. Works on Windows, macOS, and Linux.</p></div></div>{capabilities?.destinations.map(value => <label className="folder-choice" key={value}><input type="radio" name="folder-choice" value={value} checked={destinationDraft === value} onChange={() => setDestinationDraft(value)} /><span className="folder-symbol">▱</span><span><b>{value === 'default' ? 'Downloads' : value}</b><small>{value === 'default' ? 'Default save folder' : 'Configured save folder'}</small></span></label>)}<div className="dialog-actions"><button className="bevel-btn" value="cancel">Keep current</button><button className="bevel-btn primary" value="choose" onClick={() => updateSettings({ destination: destinationDraft })}>Use this folder</button></div></form></dialog>
      <div className={`demo-toast${toast ? ' show' : ''}`} role="status" aria-live="polite">{toast}</div>
    </main>
  )
}
