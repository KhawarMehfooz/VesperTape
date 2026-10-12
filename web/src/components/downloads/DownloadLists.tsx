import type { useJobs } from '../../hooks/useJobs'
import Icon from '../Icon'
import DownloadItem from './DownloadItem'

export default function DownloadLists({ queue }: { queue: ReturnType<typeof useJobs> }) {
  const row = (job: (typeof queue.active)[number]) => (
    <DownloadItem
      key={job.id}
      job={job}
      busy={queue.busy.has(job.id)}
      onAction={(item, action) => void queue.control(item, action)}
    />
  )
  return (
    <>
      <section aria-label="Download queue">
        <div className="queue-head">
          <h2>
            <Icon name="queue" />
            Your downloads
          </h2>
          <span>{queue.active.length} in progress</span>
        </div>
        {queue.error && (
          <div className="preview-message error" role="alert">
            {queue.error}
          </div>
        )}
        {queue.disconnected && (
          <div className="queue-note" role="status">
            Live updates disconnected. Reconnecting…
          </div>
        )}
        <div className="download-list" aria-live="polite">
          {queue.active.map(row)}
        </div>
        {!queue.active.length && <div className="empty-queue">No downloads queued yet.</div>}
      </section>
      <section className="history-panel" aria-label="Recent downloads">
        <div className="queue-head">
          <h2 className="history-title">Recent downloads</h2>
          <span>{queue.recent.length} items</span>
        </div>
        {queue.recent.map(row)}
        {!queue.recent.length && (
          <div className="empty-queue">Your saved downloads will appear here.</div>
        )}
      </section>
    </>
  )
}
