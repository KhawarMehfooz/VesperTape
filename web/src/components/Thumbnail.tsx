type Props = { url?: string | null; title: string }

export default function Thumbnail({ url, title }: Props) {
  return (
    <div className="download-thumbnail">
      {url ? (
        <img
          src={url}
          alt={`Thumbnail for ${title}`}
          loading="lazy"
          referrerPolicy="no-referrer"
          onLoad={(event) => {
            event.currentTarget.style.visibility = 'visible'
          }}
          onError={(event) => {
            event.currentTarget.style.visibility = 'hidden'
          }}
        />
      ) : (
        <span>Preview unavailable</span>
      )}
    </div>
  )
}
