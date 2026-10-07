import { useEffect, useState } from 'react'
import { api } from '../api/client'
import type { DownloadSettings, SettingsResponse } from '../api/contracts'
import { compatibleFormats } from '../utils/downloadSettings'

export function useDownloadSettings() {
  const [capabilities, setCapabilities] = useState<SettingsResponse | null>(null)
  const [settings, setSettings] = useState<DownloadSettings | null>(null)
  const [error, setError] = useState('')
  const [attempt, setAttempt] = useState(0)

  useEffect(() => {
    const controller = new AbortController()
    setError('')
    async function load() {
      try {
        const data = await api.settings(controller.signal)
        const formats = compatibleFormats(data.defaults.mode, data.allowed_formats)
        setCapabilities(data)
        setSettings({
          ...data.defaults,
          format: formats.includes(data.defaults.format)
            ? data.defaults.format
            : (formats[0] ?? 'auto'),
        })
      } catch {
        if (!controller.signal.aborted) setError('Could not load download settings. Please retry.')
      }
    }
    void load()
    return () => controller.abort()
  }, [attempt])

  return {
    capabilities,
    settings,
    error,
    retry: () => setAttempt((value) => value + 1),
    update: (patch: Partial<DownloadSettings>) =>
      setSettings((current) => (current ? { ...current, ...patch } : current)),
  }
}
