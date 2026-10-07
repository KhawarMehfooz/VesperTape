import type { DownloadSettings } from '../../api/contracts'
import { destinationLabel } from '../../utils/downloadSettings'
import type { UpdateSettings } from '../../utils/downloadSettings'
import Icon from '../Icon'
import FolderPicker from './FolderPicker'

type Props = {
  settings: DownloadSettings
  destinations: string[]
  rename: boolean
  onRename: (rename: boolean) => void
  onChange: UpdateSettings
}

export default function SaveSettings({
  settings,
  destinations,
  rename,
  onRename,
  onChange,
}: Props) {
  return (
    <div className="save-options">
      <section className="save-block">
        <label className="save-label" htmlFor="save-path">
          <Icon name="folder" />
          Where should it go?
        </label>
        <div className="path-row">
          <input
            className="url-input"
            id="save-path"
            type="text"
            aria-label="Save location"
            value={destinationLabel(settings.destination)}
            readOnly
          />
          <FolderPicker
            destination={settings.destination}
            destinations={destinations}
            onChange={(destination) => onChange({ destination })}
          />
        </div>
      </section>
      <section className="save-block rename-setting">
        <div className="save-label">
          <Icon name="rename" />
          Give it a name
        </div>
        <label className="check">
          <input
            className="rename-check"
            type="checkbox"
            checked={rename}
            onChange={(event) => onRename(event.target.checked)}
          />
          Choose my own file name
        </label>
        <input
          className="url-input rename-input"
          type="text"
          aria-label="New file name"
          value={settings.filename ?? ''}
          onChange={(event) => onChange({ filename: event.target.value })}
          placeholder="Enter a new file name"
        />
        <div className="save-hint">Leave unchecked to keep the source title.</div>
      </section>
    </div>
  )
}
