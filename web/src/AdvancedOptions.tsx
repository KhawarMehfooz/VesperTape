import type { DownloadSettings } from './api/contracts'

type Props = {
  settings: DownloadSettings
  updateSettings: (patch: Partial<DownloadSettings>) => void
  cookieFileAvailable: boolean
}

export default function AdvancedOptions({ settings: s, updateSettings: update, cookieFileAvailable }: Props) {
  const check = (key: keyof DownloadSettings, label: string, disabled = false) => <label className="check"><input type="checkbox" checked={Boolean(s[key])} disabled={disabled} onChange={e => update({ [key]: e.target.checked })} />{label}</label>
  const number = (key: keyof DownloadSettings, label: string, min: number, max?: number) => <label className="setting"><span className="setting-title">{label}</span><input aria-label={label} className="adv-input" type="number" min={min} max={max} value={s[key] as number ?? ''} onChange={e => update({ [key]: e.target.value === '' ? null : Number(e.target.value) })} /></label>
  const select = (key: keyof DownloadSettings, label: string, values: string[]) => <label className="setting"><span className="setting-title">{label}</span><select aria-label={label} className="fake-select" value={s[key] as string} onChange={e => update({ [key]: e.target.value })}>{values.map(value => <option key={value} value={value}>{value}</option>)}</select></label>
  return <details className="advanced-options">
    <summary>More ways to customize <span>subtitles · playlists · network</span></summary>
    <div className="adv-grid">
      <section className="adv-card"><h3>Subtitles & captions</h3>
        {check('subtitles', 'Download uploaded subtitles')}
        {check('automatic_captions', 'Include auto-generated captions')}
        <label className="setting"><span className="setting-title">Subtitle languages</span><input aria-label="Subtitle languages" className="adv-input" defaultValue={(s.subtitle_languages ?? ['en']).join(', ')} onBlur={e => update({ subtitle_languages: e.target.value.split(',').map(v => v.trim()) })} /></label>
        <div className="adv-note">Comma-separated language codes, such as en, en-US, or all.</div>
        {select('subtitle_format', 'Subtitle format', ['best', 'srt', 'vtt', 'ass'])}
        {check('embed_subtitles', 'Embed subtitles in video', s.mode === 'audio')}
      </section>
      <section className="adv-card"><h3>Metadata & post-processing</h3>
        {check('embed_metadata', 'Embed metadata')}
        {check('save_thumbnail', 'Save thumbnail as a separate file')}
        {check('embed_thumbnail', 'Embed thumbnail when supported')}
        {check('embed_chapters', 'Keep chapter markers')}
        {check('split_chapters', 'Split chapters into separate files')}
        {s.mode === 'video' && select('remux', 'Remux video container', ['auto', 'mp4', 'mkv', 'webm'])}
        <div className="adv-note">Embedding depends on the chosen container and available source metadata.</div>
      </section>
      <section className="adv-card"><h3>Playlist & archive</h3>
        {check('use_archive', 'Skip items already in the server archive')}
        <div className="adv-pair">{number('playlist_start', 'Playlist start item', 1, 100000)}{number('playlist_end', 'Playlist end item', 1, 100000)}</div>
        <div className="adv-pair">{number('minimum_duration', 'Minimum duration (seconds)', 0)}{number('maximum_duration', 'Maximum duration (seconds)', 0)}</div>
        <div className="adv-note">Filters apply to the selection above. Blank end or duration means no limit. The archive is shared across archive-enabled jobs.</div>
      </section>
      <section className="adv-card"><h3>File handling</h3>
        <label className="setting"><span className="setting-title">Output template</span><input aria-label="Output template" className="adv-input" value={s.output_template ?? ''} placeholder="%(title).120B" onChange={e => update({ output_template: e.target.value || null })} /></label>
        <div className="adv-note">Filename stem only. Supports title, id, uploader, and playlist_index. Media ID and playlist index are added for uniqueness. Use either this or your own file name.</div>
        {select('file_conflict', 'If filename already exists', ['rename', 'skip', 'fail'])}
        <div className="adv-note">Rename adds a number suffix. Skip keeps the existing file; fail reports a conflict.</div>
      </section>
      <section className="adv-card"><h3>Network & retries</h3>
        <div className="adv-pair">{number('retry_count', 'Retries', 0, 20)}{number('fragment_concurrency', 'Concurrent fragments', 1, 16)}</div>
        {number('rate_limit', 'Rate limit (bytes per second)', 1, 1000000000)}
        <label className="setting"><span className="setting-title">Proxy</span><input aria-label="Proxy" className="adv-input" value={s.proxy ?? ''} placeholder="https://proxy.example:8080" onChange={e => update({ proxy: e.target.value || null })} /></label>
        <label className="setting"><span className="setting-title">Additional HTTP headers</span><textarea aria-label="Additional HTTP headers" className="adv-textarea" defaultValue={(s.http_headers ?? []).join('\n')} placeholder="User-Agent: VesperTape" onBlur={e => update({ http_headers: e.target.value.split('\n').filter(v => v.trim()) })} /></label>
        <div className="adv-note">One header per line: User-Agent, Referer, Origin, or Accept-Language. Proxy credentials and authentication headers are not accepted.</div>
      </section>
      <section className="adv-card"><h3>Access & authentication</h3>
        {check('use_cookie_file', 'Use server cookie file', !cookieFileAvailable)}
        <div className="adv-note">{cookieFileAvailable ? 'A protected cookie file is configured on the downloader host. Previews use it automatically.' : 'Configure a protected cookie file on the downloader host to enable this option.'} Browser cookies must be available on that host; they do not come from your current device.</div>
      </section>
      <section className="adv-card"><h3>Custom yt-dlp options</h3>
        {(['--prefer-free-formats', '--no-playlist', '--playlist-reverse', '--check-formats'] as const).map(option => <label className="check" key={option}><input type="checkbox" checked={(s.custom_options ?? []).includes(option)} onChange={e => update({ custom_options: e.target.checked ? [...(s.custom_options ?? []), option] : s.custom_options.filter(v => v !== option) })} />{option}</label>)}
        <div className="adv-note">Only these allowlisted options are accepted by the server.</div>
      </section>
    </div>
  </details>
}
