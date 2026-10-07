export default function AdvancedOptions() {
  return (
<details className="advanced-options">
<summary>More ways to customize <span>subtitles · playlists · quality</span>
</summary>
<p className="adv-note">These advanced settings are not available yet.</p>
<fieldset className="unavailable-options" disabled>
<div className="adv-grid">
<section className="adv-card">
<h3>Format selection</h3>
<div className="setting">
<div className="setting-title">Format rule</div>
<select className="fake-select">
<option>Best video + best audio</option>
<option>Best single-file format</option>
<option>Best video only</option>
<option>Custom format selector</option>
</select>
</div>
<div className="setting">
<div className="setting-title">Sort preference</div>
<select className="fake-select">
<option>Resolution, then codec</option>
<option>File size, then resolution</option>
<option>Frame rate, then resolution</option>
<option>Source preference</option>
</select>
</div>
<label className="check">
<input type="checkbox" defaultChecked /> Verify selected formats are downloadable</label>
<label className="check">
<input type="checkbox" /> Allow multiple audio/video streams</label>
</section>
<section className="adv-card">
<h3>Subtitles & captions</h3>
<label className="check">
<input type="checkbox" /> Download uploaded subtitles</label>
<label className="check">
<input type="checkbox" /> Include auto-generated captions</label>
<div className="adv-pair" style={{ marginTop: '7px' }}>
<div>
<div className="setting-title">Languages</div>
<input className="adv-input" type="text" defaultValue="en" aria-label="Subtitle languages" />
</div>
<div>
<div className="setting-title">Subtitle format</div>
<select className="fake-select">
<option>SRT</option>
<option>VTT</option>
<option>ASS</option>
<option>Best available</option>
</select>
</div>
</div>
<label className="check">
<input type="checkbox" defaultChecked /> Embed subtitles in video when possible</label>
</section>
<section className="adv-card">
<h3>Playlist & archive</h3>
<label className="check">
<input type="checkbox" /> Skip items already in download archive</label>
<label className="check">
<input type="checkbox" /> Keep playlist folders and numbering</label>
<div className="adv-pair" style={{ marginTop: '7px' }}>
<div>
<div className="setting-title">Maximum items</div>
<input className="adv-input" type="number" min="1" defaultValue="0" aria-label="Maximum playlist items" />
</div>
<div>
<div className="setting-title">Start at item</div>
<input className="adv-input" type="number" min="1" defaultValue="1" aria-label="Playlist start item" />
</div>
</div>
<div className="setting-title" style={{ marginTop: '7px' }}>Optional item filter</div>
<input className="adv-input" type="text" placeholder="Date range or minimum views" />
<div className="adv-note">Maximum 0 means no limit. Playlist selection is also available above.</div>
</section>
<section className="adv-card">
<h3>Network & retries</h3>
<div className="adv-pair">
<div>
<div className="setting-title">Rate limit</div>
<input className="adv-input" type="text" placeholder="No limit" />
</div>
<div>
<div className="setting-title">Retries</div>
<input className="adv-input" type="number" min="0" defaultValue="10" />
</div>
</div>
<div className="adv-pair" style={{ marginTop: '7px' }}>
<div>
<div className="setting-title">Concurrent fragments</div>
<input className="adv-input" type="number" min="1" defaultValue="1" />
</div>
<div>
<div className="setting-title">Proxy</div>
<input className="adv-input" type="text" placeholder="Optional proxy URL" />
</div>
</div>
<div className="setting-title" style={{ marginTop: '7px' }}>Additional HTTP headers</div>
<textarea className="adv-textarea" placeholder="One header per line">
</textarea>
</section>
<section className="adv-card">
<h3>Access & authentication</h3>
<div className="auth-settings">
<div className="setting-title">Cookie source</div>
<div className="auth-modes" role="radiogroup" aria-label="Cookie source">
<div className="auth-mode">
<input type="radio" name="auth-a" id="auth-none-a" defaultChecked />
<label htmlFor="auth-none-a">None</label>
</div>
<div className="auth-mode">
<input className="browser-cookie-choice" type="radio" name="auth-a" id="auth-browser-a" />
<label htmlFor="auth-browser-a">Browser</label>
</div>
<div className="auth-mode">
<input className="cookie-file-choice" type="radio" name="auth-a" id="auth-file-a" />
<label htmlFor="auth-file-a">Cookie file</label>
</div>
</div>
<div className="cookie-panel browser-cookie-fields">
<div className="adv-pair">
<div>
<div className="setting-title">Browser</div>
<select className="fake-select">
<option>Chrome</option>
<option>Chromium</option>
<option>Firefox</option>
<option>Edge</option>
<option>Brave</option>
<option>Vivaldi</option>
<option>Opera</option>
</select>
</div>
<div>
<div className="setting-title">Profile</div>
<input className="adv-input" type="text" defaultValue="Default" aria-label="Browser profile" />
</div>
</div>
<label className="check">
<input type="checkbox" defaultChecked /> Use browser keyring when available</label>
<div className="adv-note">yt-dlp reads this profile on the downloader host. A browser on your current device is not shared automatically.</div>
</div>
<div className="cookie-panel cookie-file-fields">
<div className="setting-title">Cookie file on downloader host</div>
<div className="path-row">
<input className="url-input" type="text" placeholder="/config/cookies.txt" aria-label="Cookie file path" />
<button className="bevel-btn" type="button">BROWSE</button>
</div>
<div className="adv-note">Use a protected Netscape-format cookie file. Avoid pasting cookie contents here.</div>
</div>
</div>
<label className="check">
<input type="checkbox" /> Use credentials stored on the server</label>
<label className="check">
<input type="checkbox" /> Allow geo-bypass when supported</label>
<div className="adv-note">Your sign-in details stay on your VesperTape server.</div>
</section>
<section className="adv-card">
<h3>Metadata & post-processing</h3>
<label className="check">
<input type="checkbox" defaultChecked /> Embed metadata</label>
<label className="check">
<input type="checkbox" /> Write description and info JSON files</label>
<label className="check">
<input type="checkbox" /> Save thumbnail as a separate file</label>
<label className="check">
<input type="checkbox" /> Split chapters into separate files</label>
<div className="setting-title" style={{ marginTop: '7px' }}>Remux video container</div>
<select className="fake-select">
<option>Keep source / best compatible</option>
<option>MP4</option>
<option>MKV</option>
<option>WebM</option>
</select>
</section>
<section className="adv-card">
<h3>File handling</h3>
<div className="setting-title">Temporary files folder</div>
<input className="adv-input" type="text" placeholder="Use default temporary folder" />
<div className="adv-pair" style={{ marginTop: '7px' }}>
<div>
<div className="setting-title">Subtitle folder</div>
<input className="adv-input" type="text" placeholder="Same as download" />
</div>
<div>
<div className="setting-title">Thumbnail folder</div>
<input className="adv-input" type="text" placeholder="Same as download" />
</div>
</div>
<div className="setting-title" style={{ marginTop: '7px' }}>If filename already exists</div>
<select className="fake-select">
<option>Skip existing file</option>
<option>Ask before replacing</option>
<option>Overwrite</option>
<option>Add a number suffix</option>
</select>
</section>
<section className="adv-card">
<h3>Custom yt-dlp arguments</h3>
<div className="adv-note" style={{ margin: '0 0 6px' }}>For options without a dedicated control. For advanced users: add one extra yt-dlp option per line.</div>
<textarea className="adv-textarea" style={{ minHeight: '69px' }} placeholder="--option-name&#10;--another-option=value">
</textarea>
<div className="adv-note">Arguments should be validated by the server before a job is queued.</div>
</section>
</div>
</fieldset>
</details>
  )
}
