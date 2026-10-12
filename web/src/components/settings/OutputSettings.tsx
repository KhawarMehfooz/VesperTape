import type { DownloadSettings, SettingsResponse } from '../../api/contracts'
import {
  compatibleFormats,
  formatLabels,
  qualityLabels,
  settingsForMode,
} from '../../utils/downloadSettings'
import type { UpdateSettings } from '../../utils/downloadSettings'
import Icon from '../Icon'

type Props = {
  settings: DownloadSettings
  capabilities: SettingsResponse
  onChange: UpdateSettings
}

export default function OutputSettings({ settings, capabilities, onChange }: Props) {
  const formats = compatibleFormats(settings.mode, capabilities.allowed_formats)
  const audio = settings.mode === 'audio'
  return (
    <>
      <div className="config-layout">
        <section className="mode-plate">
          <div className="plate-head">Save as</div>
          <div className="mode-list">
            {(['audio', 'video'] as const)
              .filter((mode) => capabilities.allowed_modes.includes(mode))
              .map((mode) => (
                <div className="mode" key={mode}>
                  <input
                    className={`${mode}-choice`}
                    type="radio"
                    id={`mode-${mode}`}
                    name="download-mode"
                    checked={settings.mode === mode}
                    onChange={() =>
                      onChange(settingsForMode(settings, mode, capabilities.allowed_formats))
                    }
                  />
                  <label htmlFor={`mode-${mode}`}>
                    <Icon name={mode} />
                    {mode === 'audio' ? 'Audio' : 'Video'}
                  </label>
                </div>
              ))}
          </div>
          <div className="fine-print option-hint">Choose output type</div>
        </section>
        <section className="options-plate">
          <div key={settings.mode} className={`format-panel ${settings.mode}-panel`}>
            <div className="plate-head">
              {audio ? 'Audio format & quality' : 'Video quality & format'}
            </div>
            <div className="format-options">
              <div className="setting">
                <label className="setting-title" htmlFor="quality">
                  {audio ? 'Audio quality' : 'Resolution'}
                </label>
                {audio ? (
                  <select className="fake-select" id="quality" value="best" disabled>
                    <option value="best">Best available audio</option>
                  </select>
                ) : (
                  <select
                    className="fake-select"
                    id="quality"
                    value={settings.quality}
                    onChange={(event) =>
                      onChange({ quality: event.target.value as DownloadSettings['quality'] })
                    }
                  >
                    {capabilities.allowed_qualities.map((quality) => (
                      <option key={quality} value={quality}>
                        {qualityLabels[quality]}
                      </option>
                    ))}
                  </select>
                )}
              </div>
              <div className="setting">
                <label className="setting-title" htmlFor="format">
                  {audio ? 'Audio format' : 'Container'}
                </label>
                <select
                  className="fake-select"
                  id="format"
                  value={formats.includes(settings.format) ? settings.format : ''}
                  onChange={(event) =>
                    onChange({ format: event.target.value as DownloadSettings['format'] })
                  }
                >
                  {!formats.length && <option value="">No compatible formats</option>}
                  {formats.map((format) => (
                    <option key={format} value={format}>
                      {formatLabels[format]}
                    </option>
                  ))}
                </select>
              </div>
            </div>
            {!audio && (
              <label className="check">
                <input type="checkbox" checked disabled />
                Merge best audio and video streams
              </label>
            )}
            {audio && (
              <div className="fine-print option-hint">Uses the best available audio stream.</div>
            )}
          </div>
        </section>
      </div>
      {!formats.length && (
        <p className="preview-message error" role="alert">
          The server has no allowed formats for this mode. Choose another mode.
        </p>
      )}
    </>
  )
}
