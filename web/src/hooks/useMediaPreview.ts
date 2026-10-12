import { useEffect, useRef, useState } from 'react'
import { api, ApiRequestError } from '../api/client'
import type { PlaylistSelection, PreviewResponse } from '../api/contracts'
import { youtubeLinkError } from '../api/youtube'

export type SelectionMode = 'all' | 'one' | 'range'
const previewTimeout = 30_000

export function useMediaPreview() {
  const [url, setUrl] = useState('')
  const [preview, setPreview] = useState<PreviewResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [mode, setMode] = useState<SelectionMode>('all')
  const [start, setStart] = useState(1)
  const [end, setEnd] = useState(1)
  const requestId = useRef(0)
  const abort = useRef<AbortController | null>(null)
  const linkError = url.trim() ? youtubeLinkError(url) : null
  const indices =
    preview?.items.flatMap((item) => (item.playlist_index == null ? [] : [item.playlist_index])) ??
    []
  const selection: PlaylistSelection = {
    item_indices:
      mode === 'all'
        ? []
        : mode === 'one'
          ? [start]
          : indices.filter((index) => index >= start && index <= end),
  }
  const validSelection =
    mode === 'all' ||
    (indices.includes(start) && (mode === 'one' || (end >= start && indices.includes(end))))
  const selectedItems =
    preview?.items.filter(
      (item) => mode === 'all' || selection.item_indices.includes(item.playlist_index ?? 1),
    ) ?? []
  const hasMedia = selectedItems.some(
    (item) => item.formats_checked === false || item.formats.length > 0,
  )
  const formatsDeferred = selectedItems.some((item) => item.formats_checked === false)

  useEffect(
    () => () => {
      requestId.current += 1
      abort.current?.abort()
    },
    [],
  )

  function reset() {
    requestId.current += 1
    abort.current?.abort()
    setPreview(null)
    setError('')
    setLoading(false)
  }

  async function inspect() {
    reset()
    const validationError = youtubeLinkError(url)
    if (validationError) {
      setError(validationError)
      return
    }
    const id = requestId.current
    const controller = new AbortController()
    abort.current = controller
    setLoading(true)
    let timedOut = false
    const timeout = window.setTimeout(() => {
      timedOut = true
      controller.abort()
    }, previewTimeout)
    try {
      const data = await api.preview(url, controller.signal)
      if (id !== requestId.current) return
      setPreview(data)
      setMode('all')
      setStart(data.items[0]?.playlist_index ?? 1)
      setEnd(data.items.at(-1)?.playlist_index ?? 1)
    } catch (failure) {
      if (id === requestId.current)
        setError(
          failure instanceof ApiRequestError
            ? failure.message
            : timedOut
              ? 'Preview took too long. Please try again; the source may be slow or unavailable.'
              : 'Could not reach the preview service. Please try again.',
        )
    } finally {
      window.clearTimeout(timeout)
      if (id === requestId.current) setLoading(false)
    }
  }

  return {
    url,
    preview,
    loading,
    error,
    linkError,
    mode,
    start,
    end,
    selection,
    validSelection,
    hasMedia,
    formatsDeferred,
    firstItem: selectedItems[0] ?? preview?.items[0],
    changeUrl: (value: string) => {
      reset()
      setUrl(value)
    },
    inspect,
    setMode,
    setStart,
    setEnd,
  }
}

export type MediaPreview = ReturnType<typeof useMediaPreview>
