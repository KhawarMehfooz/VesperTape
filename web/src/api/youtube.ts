const videoId = /^[A-Za-z0-9_-]{11}$/
const playlistId = /^[A-Za-z0-9_-]{2,150}$/
const youtubeHosts = ['youtube.com', 'www.youtube.com', 'm.youtube.com', 'music.youtube.com']
const shortHosts = ['youtu.be', 'www.youtu.be']
const embedHosts = ['youtube-nocookie.com', 'www.youtube-nocookie.com']

/** Syntax validation only; preview checks whether the media is accessible. */
export function youtubeLinkError(value: string): string | null {
  const link = value.trim()
  let url: URL
  try {
    url = new URL(link)
  } catch {
    return 'Provide a valid YouTube HTTP or HTTPS link.'
  }
  if (
    !/^https?:\/\//i.test(link) ||
    !['http:', 'https:'].includes(url.protocol) ||
    url.username ||
    url.password ||
    /^[^/]+:\/\/[^/]*@/.test(link) ||
    url.port ||
    /[\s\\\x00-\x1f]/.test(link)
  ) {
    return 'Provide a valid YouTube HTTP or HTTPS link.'
  }
  if (![...youtubeHosts, ...shortHosts, ...embedHosts].includes(url.hostname))
    return 'Only YouTube links are supported.'
  const path = url.pathname.replace(/\/+$/, '')
  const singleId = (name: string, pattern: RegExp) => {
    const values = url.searchParams.getAll(name)
    return values.length === 1 && pattern.exec(values[0])?.[0] === values[0]
  }
  let valid: boolean
  if (shortHosts.includes(url.hostname)) valid = videoId.test(path.replace(/^\//, ''))
  else if (embedHosts.includes(url.hostname)) valid = /^\/embed\/[A-Za-z0-9_-]{11}$/.test(path)
  else if (path === '/watch') valid = singleId('v', videoId)
  else if (path === '/playlist') valid = singleId('list', playlistId)
  else valid = /^\/(shorts|live|embed)\/[A-Za-z0-9_-]{11}$/.test(path)
  if (!valid) return 'Provide a valid YouTube video or playlist link.'
  if (url.searchParams.has('list') && !singleId('list', playlistId))
    return 'Provide a valid YouTube playlist ID.'
  return null
}
