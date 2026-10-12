import { useRef, useState } from 'react'
import { createPortal } from 'react-dom'

type Props = {
  destination: string
  destinations: string[]
  onChange: (destination: string) => void
}

export default function FolderPicker({ destination, destinations, onChange }: Props) {
  const dialog = useRef<HTMLDialogElement>(null)
  const [draft, setDraft] = useState(destination)
  return (
    <>
      <button
        className="bevel-btn"
        type="button"
        onClick={() => {
          setDraft(destination)
          dialog.current?.showModal()
        }}
      >
        Choose folder
      </button>
      {createPortal(
        <dialog className="location-dialog" ref={dialog} aria-labelledby="location-title">
          <form method="dialog" onSubmit={(event) => event.stopPropagation()}>
            <div className="dialog-heading">
              <span className="dialog-folder">✦</span>
              <div>
                <h2 id="location-title">Choose a cozy spot</h2>
                <p>
                  Docker maps these folder names to locations you choose during setup. Works on
                  Windows, macOS, and Linux.
                </p>
              </div>
            </div>
            {destinations.map((value) => (
              <label className="folder-choice" key={value}>
                <input
                  type="radio"
                  name="folder-choice"
                  value={value}
                  checked={draft === value}
                  onChange={() => setDraft(value)}
                />
                <span className="folder-symbol">▱</span>
                <span>
                  <b>{value === 'default' ? 'Downloads' : value}</b>
                  <small>
                    {value === 'default' ? 'Default save folder' : 'Configured save folder'}
                  </small>
                </span>
              </label>
            ))}
            <div className="dialog-actions">
              <button className="bevel-btn" value="cancel">
                Keep current
              </button>
              <button className="bevel-btn primary" value="choose" onClick={() => onChange(draft)}>
                Use this folder
              </button>
            </div>
          </form>
        </dialog>,
        document.body,
      )}
    </>
  )
}
