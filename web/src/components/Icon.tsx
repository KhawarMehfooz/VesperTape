type IconName =
  | 'audio'
  | 'video'
  | 'paste'
  | 'preview'
  | 'folder'
  | 'rename'
  | 'download'
  | 'queue'
  | 'check'
  | 'warning'

export default function Icon({ name }: { name: IconName }) {
  return (
    <svg className="icon" viewBox="0 0 24 24" aria-hidden="true">
      {name === 'check' && <path d="m5 12 4 4L19 6" />}
      {name === 'warning' && (
        <>
          <path d="M12 3 2 21h20L12 3Z" />
          <path d="M12 9v5m0 3v1" />
        </>
      )}
      {name === 'audio' && (
        <>
          <path d="M9 18V5l12-2v13M9 9l12-2" />
          <circle cx="6" cy="18" r="3" />
          <circle cx="18" cy="16" r="3" />
        </>
      )}
      {name === 'video' && (
        <>
          <rect x="3" y="5" width="18" height="14" rx="2" />
          <path d="m10 9 5 3-5 3z" />
        </>
      )}
      {name === 'paste' && (
        <>
          <path d="M8 5H6a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2v-2M9 3h6l1 3H8l1-3Z" />
          <path d="M13 15h7m-3-3 3 3-3 3" />
        </>
      )}
      {name === 'preview' && (
        <>
          <circle cx="10.8" cy="10.8" r="6.8" />
          <path d="m16 16 4.5 4.5" />
        </>
      )}
      {name === 'folder' && (
        <>
          <path d="M3 7a2 2 0 0 1 2-2h5l2 2h7a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z" />
          <path d="M3 10h18" />
        </>
      )}
      {name === 'rename' && (
        <>
          <path d="M12 20h9" />
          <path d="m16.5 3.5 4 4L8 20l-5 1 1-5z" />
        </>
      )}
      {name === 'download' && (
        <>
          <path d="M12 3v12m-5-5 5 5 5-5" />
          <path d="M5 17v3h14v-3" />
        </>
      )}
      {name === 'queue' && (
        <>
          <path d="M4 5h16M4 12h16M4 19h16" />
          <circle cx="7" cy="5" r="1" />
          <circle cx="7" cy="12" r="1" />
          <circle cx="7" cy="19" r="1" />
        </>
      )}
    </svg>
  )
}
