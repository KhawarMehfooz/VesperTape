import type { ApiError } from '../../api/contracts'

export default function SubmissionError({ error }: { error: ApiError | null }) {
  if (!error) return null
  return (
    <div className="submission-error" role="alert">
      <p>{error.message}</p>
      {error.details.length > 0 && (
        <ul>
          {error.details.map((detail, index) => (
            <li key={index}>
              {detail.location.filter((part) => part !== 'body').join(' › ')}: {detail.message}
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
