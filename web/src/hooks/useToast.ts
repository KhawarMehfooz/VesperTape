import { useEffect, useState } from 'react'

export function useToast() {
  const [message, show] = useState('')
  useEffect(() => {
    if (!message) return
    const timeout = window.setTimeout(() => show(''), 2500)
    return () => window.clearTimeout(timeout)
  }, [message])
  return { message, show }
}
