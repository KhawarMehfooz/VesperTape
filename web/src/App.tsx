import DownloadForm from './components/DownloadForm'
import DownloadLists from './components/downloads/DownloadLists'
import { useJobs } from './hooks/useJobs'

export default function App() {
  const queue = useJobs()
  return (
    <main className="shell">
      <section className="variant variant-a" aria-label="Classic Download Window">
        <div className="skin">
          <div className="titlebar">
            <div className="title-name">
              <span className="mark">✣</span> VESPERTAPE DOWNLOAD MANAGER
            </div>
            <div className="window-buttons" aria-hidden="true">
              <i />
              <i />
              <i />
            </div>
          </div>
          <DownloadForm onCreated={queue.add} />
          <DownloadLists queue={queue} />
        </div>
      </section>
    </main>
  )
}
