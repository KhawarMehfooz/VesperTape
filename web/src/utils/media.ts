import type { DownloadedItem, JobResponse } from '../api/contracts'

const mediaExtension = /\.(mp4|webm|mkv|mp3|m4a|flac|wav|opus|ogg|aac|mov)$/i

export function thumbnailFromFilename(filename: string) {
  const id = filename.match(/\[([A-Za-z0-9_-]{11})\]/)?.[1]
  return id ? `https://i.ytimg.com/vi/${id}/hqdefault.jpg` : null
}

export function jobThumbnail(job: JobResponse) {
  return (
    job.thumbnail_url ??
    thumbnailFromFilename(
      job.output_name ?? (job.source_url ?? '').replace(/.*[?&]v=([A-Za-z0-9_-]{11}).*/, '[$1]'),
    )
  )
}

export function downloadedMedia(job: JobResponse): DownloadedItem[] {
  const items = job.downloaded_items?.length
    ? job.downloaded_items
    : (job.output_files ?? []).map((filename) => ({
        filename,
        title: filename.replace(/\s*\[[A-Za-z0-9_-]{11}\].*$/, '').replaceAll('_', ' '),
        thumbnail_url: thumbnailFromFilename(filename),
      }))
  const index = (filename: string) => Number(filename.match(/\] (\d+)(?: \(\d+\))?\./)?.[1] ?? 0)
  return items
    .filter((item) => mediaExtension.test(item.filename))
    .sort((a, b) => index(a.filename) - index(b.filename))
}

export function durationLabel(seconds: number | null | undefined) {
  return seconds == null
    ? 'Duration unavailable'
    : `${Math.floor(seconds / 60)}:${String(Math.floor(seconds % 60)).padStart(2, '0')}`
}
