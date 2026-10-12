import Icon from '../Icon'
import PlaylistSelection from './PlaylistSelection'
import type { MediaPreview as PreviewState, SelectionMode } from '../../hooks/useMediaPreview'
import { durationLabel } from '../../utils/media'

type Props = { media: PreviewState; disabled: boolean; onModeChange: (mode: SelectionMode) => void }

export default function MediaPreview({ media, disabled, onModeChange }: Props) {
  const { preview, firstItem, hasMedia, formatsDeferred } = media
  if (!preview) return null
  return (
    <div className="preview-reveal">
      <div className="preview-reveal-content">
        <article className="source-preview">
          <div
            className={`preview-art${firstItem?.thumbnail_url ? ' has-image' : ''}`}
            aria-hidden="true"
          >
            {firstItem?.thumbnail_url ? (
              <img src={firstItem.thumbnail_url} alt="" referrerPolicy="no-referrer" />
            ) : (
              <span>✣</span>
            )}
          </div>
          <div>
            <div className="preview-top">
              <h3 className="preview-title">{preview.title}</h3>
              <div className={`preview-status${hasMedia ? '' : ' is-warning'}`}>
                <Icon name={hasMedia ? 'check' : 'warning'} />
                {formatsDeferred ? 'Playlist listed' : hasMedia ? 'Looks good' : 'No formats'}
              </div>
            </div>
            <div className="preview-meta">
              {firstItem?.uploader ?? 'Unknown uploader'} ·{' '}
              {durationLabel(firstItem?.duration_seconds)}
              {firstItem?.formats.some((format) => format.height === 1080) && ' · 1080p available'}
            </div>
            <PlaylistSelection media={media} disabled={disabled} onModeChange={onModeChange} />
            {!preview.items.length && (
              <div className="preview-meta" role="status">
                No playable items were found in this playlist.
              </div>
            )}
            {formatsDeferred && (
              <div className="preview-meta" role="status">
                Playlist listed. Availability and formats are checked when downloading.
              </div>
            )}
            {preview.items.length > 0 && !hasMedia && (
              <div className="preview-meta error" role="status">
                No downloadable formats are available for this item.
              </div>
            )}
          </div>
        </article>
      </div>
    </div>
  )
}
