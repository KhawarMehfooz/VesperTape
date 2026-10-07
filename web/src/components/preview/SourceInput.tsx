import Icon from '../Icon'
import { useToast } from '../../hooks/useToast'
import type { MediaPreview } from '../../hooks/useMediaPreview'

type Props = {
  media: MediaPreview
  disabled: boolean
  onChange: (url: string) => void
  onInspect: () => void
}

export default function SourceInput({ media, disabled, onChange, onInspect }: Props) {
  const toast = useToast()
  const { url, preview, firstItem, loading, linkError, error } = media

  async function pasteLink() {
    try {
      const value = await navigator.clipboard.readText()
      if (value) {
        onChange(value)
        toast.show('Link pasted. Take a look, then preview it.')
      } else toast.show('Your clipboard looks empty.')
    } catch {
      toast.show('Paste your video link into the box above.')
    }
  }

  return (
    <>
      <form
        className="link-row"
        aria-busy={loading}
        onSubmit={(event) => {
          event.preventDefault()
          onInspect()
        }}
      >
        <label className="field-label" htmlFor="source-url">
          Video link
        </label>
        <input
          className="url-input"
          id="source-url"
          disabled={disabled}
          type="text"
          inputMode="url"
          autoComplete="url"
          aria-invalid={!!linkError || !!error}
          aria-describedby={linkError || error ? 'link-error' : undefined}
          required
          value={url}
          placeholder="Paste a YouTube video or playlist link"
          onChange={(event) => onChange(event.target.value)}
        />
        <span className="url-actions">
          <button
            className="bevel-btn"
            type="button"
            disabled={disabled}
            onClick={() => void pasteLink()}
          >
            <Icon name="paste" />
            Paste link
          </button>
          <button
            className="bevel-btn inspect"
            disabled={disabled || loading || !url.trim() || !!linkError}
          >
            <Icon name="preview" />
            {loading ? 'Inspecting…' : 'Preview'}
          </button>
        </span>
      </form>
      <div className="mini-note" aria-live="polite">
        <span>
          {loading
            ? 'Inspecting media and available formats…'
            : preview
              ? `${firstItem?.uploader ?? 'Source inspected'}${preview.kind === 'playlist' ? ` · ${preview.total_items ?? preview.items.length} videos detected.` : ''}`
              : 'Paste a YouTube video or playlist link to get started.'}
        </span>
        {preview && (
          <span className="link-status">
            <Icon name="check" />
            Link ready
          </span>
        )}
      </div>
      {(linkError || error) && (
        <p id="link-error" className="preview-message error" role="alert">
          {linkError || error}
        </p>
      )}
      <div className={`demo-toast${toast.message ? ' show' : ''}`} role="status" aria-live="polite">
        {toast.message}
      </div>
    </>
  )
}
