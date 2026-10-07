import { useCallback, useEffect, useRef, useState } from 'react'
import { api, ApiRequestError, subscribeToJobs } from '../api/client'
import type { JobAction } from '../api/client'
import type { JobResponse } from '../api/contracts'

const terminalStates = new Set<JobResponse['status']>(['complete', 'failed', 'canceled'])

export function useJobs() {
  const [jobs, setJobs] = useState<JobResponse[]>([])
  const [busy, setBusy] = useState<Set<string>>(new Set())
  const locks = useRef(new Set<string>())
  const [error, setError] = useState('')
  const [disconnected, setDisconnected] = useState(false)

  useEffect(
    () =>
      subscribeToJobs(
        (snapshot) => {
          setJobs(snapshot)
          setDisconnected(false)
        },
        () => setDisconnected(true),
      ),
    [],
  )

  const add = useCallback((created: JobResponse) => {
    setJobs((current) =>
      current.some((job) => job.id === created.id) ? current : [...current, created],
    )
  }, [])

  async function control(job: JobResponse, action: JobAction) {
    if (locks.current.has(job.id)) return
    locks.current.add(job.id)
    setBusy(new Set(locks.current))
    setError('')
    try {
      await api.controlJob(job.id, action)
      // Actions refresh the server snapshot; the action response may already be stale.
      setJobs((await api.jobs()).jobs)
    } catch (failure) {
      setError(
        failure instanceof ApiRequestError
          ? failure.message
          : 'Could not confirm the download action. Check its status and try again.',
      )
    } finally {
      locks.current.delete(job.id)
      setBusy(new Set(locks.current))
    }
  }

  return {
    active: jobs.filter((job) => !terminalStates.has(job.status)),
    recent: jobs
      .filter((job) => terminalStates.has(job.status))
      .sort((a, b) => b.updated_at.localeCompare(a.updated_at)),
    busy,
    error,
    disconnected,
    add,
    control,
  }
}
