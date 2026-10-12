import type { MediaPreview, SelectionMode } from '../../hooks/useMediaPreview'

type Props = { media: MediaPreview; disabled: boolean; onModeChange: (mode: SelectionMode) => void }

export default function PlaylistSelection({ media, disabled, onModeChange }: Props) {
  const { preview, mode, start, end, setStart, setEnd, validSelection } = media
  if (!preview || preview.kind !== 'playlist') return null
  const total = preview.total_items ?? preview.items.length
  return (
    <div className="playlist-row">
      <div className="setting-title">Playlist · {total} items</div>
      <select
        className="fake-select"
        aria-label="Playlist download selection"
        disabled={disabled}
        value={mode}
        onChange={(event) => onModeChange(event.target.value as SelectionMode)}
      >
        <option value="one">
          This video only · {start} of {total}
        </option>
        <option value="all">Entire playlist · {total} videos</option>
        <option value="range">Choose a range…</option>
      </select>
      {mode !== 'all' && (
        <div className="playlist-range is-visible">
          <span>{mode === 'one' ? 'Video' : 'Videos'}</span>
          <input
            type="number"
            min="1"
            disabled={disabled}
            value={start}
            aria-label="First playlist item"
            onChange={(event) => setStart(Number(event.target.value))}
          />
          {mode === 'range' && (
            <>
              <span>to</span>
              <input
                type="number"
                min={start}
                disabled={disabled}
                value={end}
                aria-label="Last playlist item"
                onChange={(event) => setEnd(Number(event.target.value))}
              />
            </>
          )}
          <span>of {total}</span>
        </div>
      )}
      {!validSelection && (
        <div className="error" role="alert">
          Choose indexes from the preview, with the end at or after the start.
        </div>
      )}
    </div>
  )
}
