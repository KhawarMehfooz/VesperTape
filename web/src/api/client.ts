import type {
  ApiError,
  CreateJobRequest,
  JobActionRequest,
  JobResponse,
  JobsResponse,
  PreviewResponse,
  SettingsResponse,
} from './contracts'

export type JobAction = JobActionRequest['action'] | 'remove'

export class ApiRequestError extends Error {
  constructor(readonly error: ApiError) {
    super(error.message)
    this.name = 'ApiRequestError'
  }
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`/api${path}`, options)
  if (response.status === 204) return undefined as T
  const data = await response.json()
  // Job responses include their own error field; distinguish the error envelope.
  if (!response.ok || ('error' in data && !('id' in data))) {
    throw new ApiRequestError(
      data.error ?? { code: 'request_failed', message: 'The request failed.', details: [] },
    )
  }
  return data as T
}

function jsonBody(body: unknown): RequestInit {
  return {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  }
}

export const api = {
  settings: (signal: AbortSignal) => request<SettingsResponse>('/settings', { signal }),
  preview: (url: string, signal: AbortSignal) =>
    request<PreviewResponse>('/preview', { ...jsonBody({ url }), signal }),
  createJob: (input: CreateJobRequest) => request<JobResponse>('/jobs', jsonBody(input)),
  jobs: () => request<JobsResponse>('/jobs'),
  controlJob: (id: string, action: JobAction) =>
    action === 'remove'
      ? request<void>(`/jobs/${encodeURIComponent(id)}`, { method: 'DELETE' })
      : request<JobResponse>(`/jobs/${encodeURIComponent(id)}/actions`, jsonBody({ action })),
}

export function subscribeToJobs(onJobs: (jobs: JobResponse[]) => void, onDisconnected: () => void) {
  const feed = new EventSource('/api/jobs/events')
  feed.addEventListener('jobs', (event) => {
    try {
      const snapshot = JSON.parse((event as MessageEvent).data) as JobsResponse
      if (!Array.isArray(snapshot.jobs)) throw new Error('Invalid jobs snapshot')
      onJobs(snapshot.jobs)
    } catch {
      onDisconnected()
    }
  })
  feed.onerror = onDisconnected
  return () => feed.close()
}
