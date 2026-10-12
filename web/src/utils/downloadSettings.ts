import type { DownloadSettings } from '../api/contracts'

export type UpdateSettings = (patch: Partial<DownloadSettings>) => void
export type DownloadFormat = DownloadSettings['format']
export type DownloadMode = DownloadSettings['mode']

const modeFormats: Record<DownloadMode, readonly DownloadFormat[]> = {
  audio: ['auto', 'mp3', 'm4a', 'flac', 'wav'],
  video: ['auto', 'mp4', 'webm'],
}

export const qualityLabels: Record<string, string> = {
  best: 'Best available · up to 4K',
  '1080p': '1080p · Full HD',
  '720p': '720p · Compact',
  '480p': '480p · Small',
}
export const formatLabels: Record<DownloadFormat, string> = {
  auto: 'Automatic · Best compatible',
  mp4: 'MP4 · Compatible',
  webm: 'WebM · Open format',
  mp3: 'MP3',
  m4a: 'M4A · AAC',
  flac: 'FLAC · Lossless',
  wav: 'WAV',
}

export function compatibleFormats(mode: DownloadMode, allowed: string[]) {
  return allowed.filter((format): format is DownloadFormat =>
    modeFormats[mode].some((value) => value === format),
  )
}

export function settingsForMode(
  settings: DownloadSettings,
  mode: DownloadMode,
  allowed: string[],
): Partial<DownloadSettings> {
  const formats = compatibleFormats(mode, allowed)
  return {
    mode,
    ...(mode === 'audio' ? ({ remux: 'auto', embed_subtitles: false } as const) : {}),
    format: formats.includes(settings.format) ? settings.format : (formats[0] ?? 'auto'),
  }
}

export function destinationLabel(destination = 'default') {
  return destination === 'default' ? 'Downloads' : destination
}
