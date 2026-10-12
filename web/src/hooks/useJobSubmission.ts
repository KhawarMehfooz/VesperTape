import { useRef, useState } from 'react'
import { api, ApiRequestError } from '../api/client'
import type { ApiError, CreateJobRequest, JobResponse } from '../api/contracts'

export function useJobSubmission(onCreated: (job: JobResponse) => void) {
  const lock = useRef(false)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<ApiError | null>(null)
  const [notice, setNotice] = useState('')

  function clearFeedback() {
    setError(null)
    setNotice('')
  }

  async function submit(input: CreateJobRequest) {
    if (lock.current) return
    lock.current = true
    setSubmitting(true)
    clearFeedback()
    try {
      onCreated(await api.createJob(input))
      setNotice('Added to downloads.')
    } catch (failure) {
      setError(
        failure instanceof ApiRequestError
          ? failure.error
          : {
              code: 'connection_failed',
              message: 'Could not confirm submission. Check the queue before trying again.',
              details: [],
            },
      )
    } finally {
      lock.current = false
      setSubmitting(false)
    }
  }

  return { submitting, error, notice, submit, clearFeedback }
}
