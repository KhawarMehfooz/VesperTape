import { useState } from 'react'
import type { DownloadSettings, JobResponse } from '../api/contracts'
import { useDownloadSettings } from '../hooks/useDownloadSettings'
import { useJobSubmission } from '../hooks/useJobSubmission'
import { useMediaPreview } from '../hooks/useMediaPreview'
import { compatibleFormats, destinationLabel } from '../utils/downloadSettings'
import Icon from './Icon'
import SubmissionError from './forms/SubmissionError'
import SourceInput from './preview/SourceInput'
import MediaPreview from './preview/MediaPreview'
import AdvancedOptions from './settings/AdvancedOptions'
import OutputSettings from './settings/OutputSettings'
import SaveSettings from './settings/SaveSettings'

export default function DownloadForm({ onCreated }: { onCreated: (job: JobResponse) => void }) {
  const configuration = useDownloadSettings()
  const media = useMediaPreview()
  const submission = useJobSubmission(onCreated)
  const [rename, setRename] = useState(false)
  const { settings, capabilities } = configuration
  const formats =
    settings && capabilities ? compatibleFormats(settings.mode, capabilities.allowed_formats) : []
  const canSubmit =
    !media.linkError &&
    !!media.preview &&
    !!settings &&
    media.validSelection &&
    media.hasMedia &&
    formats.includes(settings.format)
  const status = !media.preview
    ? 'Ready when you are'
    : !media.validSelection
      ? 'Choose a valid playlist selection.'
      : !media.hasMedia
        ? 'No downloadable formats in this selection.'
        : 'Ready when you are'

  function updateSettings(patch: Partial<DownloadSettings>) {
    configuration.update(patch)
    submission.clearFeedback()
  }

  return (
    <div className="well">
      <h2 className="section-title">What would you like to save?</h2>
      <div className="subhead">Paste a video link and we’ll get the details ready for you.</div>
      <SourceInput
        media={media}
        disabled={submission.submitting}
        onChange={(url) => {
          media.changeUrl(url)
          submission.clearFeedback()
        }}
        onInspect={() => {
          submission.clearFeedback()
          void media.inspect()
        }}
      />
      <MediaPreview
        media={media}
        disabled={submission.submitting}
        onModeChange={(mode) => {
          media.setMode(mode)
          submission.clearFeedback()
        }}
      />
      <details className="source-feedback">
        <summary>Help · supported sources and link messages</summary>
        <div className="feedback-list">
          <span className="good">✓ Link inspected</span>
          <span className="warn">⚠ Playlist detected</span>
          <span className="bad">! Unsupported source</span>
          <span className="bad">! No compatible formats found</span>
          <span className="bad">! Invalid or private link</span>
          <span>… Inspecting source</span>
        </div>
      </details>
      {configuration.error && (
        <div className="preview-message error" role="alert">
          {configuration.error}{' '}
          <button className="bevel-btn" type="button" onClick={configuration.retry}>
            Retry settings
          </button>
        </div>
      )}
      {!settings && !configuration.error && (
        <p className="preview-message" role="status">
          Loading download settings…
        </p>
      )}
      {settings && capabilities && (
        <form
          className="config"
          aria-busy={submission.submitting}
          onSubmit={(event) => {
            event.preventDefault()
            if (!canSubmit) return
            void submission.submit({
              url: media.url.trim(),
              selection: media.selection,
              settings: {
                ...settings,
                filename: rename ? settings.filename?.trim() || null : null,
              },
            })
          }}
        >
          <fieldset className="download-options" disabled={submission.submitting}>
            <legend className="sr-only">Download settings</legend>
            <OutputSettings
              settings={settings}
              capabilities={capabilities}
              onChange={updateSettings}
            />
            <SaveSettings
              settings={settings}
              destinations={capabilities.destinations}
              rename={rename}
              onRename={(value) => {
                setRename(value)
                submission.clearFeedback()
              }}
              onChange={updateSettings}
            />
            <AdvancedOptions
              settings={settings}
              updateSettings={updateSettings}
              cookieFileAvailable={capabilities.cookie_file_available}
            />
          </fieldset>
          <SubmissionError error={submission.error} />
          <div className="actionline">
            <span className={`status${submission.notice ? ' is-success' : ''}`} role="status">
              {submission.notice && <Icon name="check" />}
              {submission.notice || status}
            </span>
            <span className="fine-print">Saved to {destinationLabel(settings.destination)}</span>
            <button className="bevel-btn primary" disabled={!canSubmit || submission.submitting}>
              <Icon name="download" />
              {submission.submitting ? 'Adding…' : 'Add to downloads'}
            </button>
          </div>
        </form>
      )}
    </div>
  )
}
