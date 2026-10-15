import type { JobResponse } from '../../api/contracts'
import { archiveSaveUrl, fileSaveUrl, type JobAction } from '../../api/client'
import { downloadedMedia, jobThumbnail } from '../../utils/media'
import Thumbnail from '../Thumbnail'

const actionsByStatus: Record<JobResponse['status'], JobAction[]> = {
  queued: ['pause', 'cancel'],
  downloading: ['pause', 'cancel'],
  paused: ['resume', 'cancel'],
  complete: ['remove'],
  canceled: ['retry', 'remove'],
  failed: ['retry', 'remove'],
}

type Props = {
  job: JobResponse
  busy: boolean
  onAction: (job: JobResponse, action: JobAction) => void
}

export default function DownloadItem({ job, busy, onAction }: Props) {
  const stateClass = job.status === 'downloading' ? 'active' : job.status
  const files = downloadedMedia(job)
  const completed = job.status === 'complete' && files.length > 0
  const showProgress = job.status === 'downloading' || job.status === 'paused'
  return (
    <article className={`queue-item is-${stateClass}${completed ? ' has-files' : ''}`}>
      {!completed && <Thumbnail url={jobThumbnail(job)} title={job.title ?? 'New download'} />}
      <div className="download-details">
        <div className="queue-name">{job.title ?? 'New download'}</div>
        <div className="queue-meta">
          {job.settings.mode === 'audio' ? 'Audio' : 'Video'} · {job.settings.quality}
          {job.output_folder ? ` · Downloads/${job.output_folder}` : ''}
          {job.status === 'complete' && !files.length ? ' · No new files' : ''}
        </div>
        {showProgress && (
          <>
            <div className="queue-extra">
              <progress
                className="progress"
                max="100"
                value={job.progress.percent ?? undefined}
                aria-label="Download progress"
              />
              <span className="queue-meta">
                {job.progress.percent == null
                  ? 'Preparing download…'
                  : `${job.progress.percent.toFixed(1)}%`}
              </span>
            </div>
            <div className="queue-meta">
              {job.progress.speed_bytes_per_second != null &&
                `${(job.progress.speed_bytes_per_second / 1048576).toFixed(2)} MB/s`}
              {job.progress.eta_seconds != null &&
                ` · ${Math.ceil(job.progress.eta_seconds)}s remaining`}
            </div>
          </>
        )}
        {job.error && <div className="queue-meta error">{job.error.message}</div>}
      </div>
      <div className="job-controls">
        <div className={`queue-state is-${stateClass}`}>{job.status.toUpperCase()}</div>
        <div className="queue-actions-inline">
          {completed && files.length > 1 && (
            <a className="small-btn" href={archiveSaveUrl([job.id])} download>
              Save all as ZIP
            </a>
          )}
          {actionsByStatus[job.status].map((action) => (
            <button
              className="small-btn"
              key={action}
              disabled={busy}
              onClick={() => onAction(job, action)}
            >
              {action[0].toUpperCase() + action.slice(1)}
            </button>
          ))}
        </div>
      </div>
      {completed && (
        <ul className="saved-items">
          {files.map((file) => (
            <li key={file.filename}>
              <Thumbnail url={file.thumbnail_url} title={file.title} />
              <div className="download-details">
                <div className="queue-name">
                  {!job.output_folder && files.length === 1
                    ? (job.title ?? file.title)
                    : file.title}
                </div>
                <div className="queue-meta">
                  {file.filename.split('.').at(-1)?.toUpperCase()} · On server
                </div>
              </div>
              <a className="small-btn" href={fileSaveUrl(job.id, file.filename)} download>
                Save to device
              </a>
            </li>
          ))}
        </ul>
      )}
    </article>
  )
}
