"""Transactional queue storage. All state changes advance a durable feed revision."""
from datetime import datetime, timezone
from uuid import uuid4

if __package__:
    from .contracts import CreateJobRequest, JobResponse, JobProgress
    from .errors import ApiException
else:
    from contracts import CreateJobRequest, JobResponse, JobProgress
    from errors import ApiException


def now():
    return datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')


class JobStore:
    def __init__(self, database):
        self.database = database

    def _save(self, connection, job):
        job.updated_at = now()
        revision = connection.execute('UPDATE queue_revision SET value=value+1 WHERE id=1 RETURNING value').fetchone()[0]
        connection.execute(
            'INSERT INTO jobs VALUES (?, ?, ?, ?) ON CONFLICT(id) DO UPDATE SET status=excluded.status, payload=excluded.payload, revision=excluded.revision',
            (job.id, job.status, job.model_dump_json(), revision),
        )
        return job

    def create(self, request: CreateJobRequest):
        timestamp = now()
        job = JobResponse(id=str(uuid4()), source_url=request.url, status='queued',
                          selection=request.selection, settings=request.settings,
                          progress=JobProgress(), created_at=timestamp, updated_at=timestamp)
        with self.database.connection() as connection:
            connection.execute('BEGIN IMMEDIATE')
            self._save(connection, job)
        return job

    def snapshot(self):
        with self.database.connection() as connection:
            connection.execute('BEGIN')
            revision = connection.execute('SELECT value FROM queue_revision WHERE id=1').fetchone()[0]
            jobs = [JobResponse.model_validate_json(row[0]) for row in connection.execute('SELECT payload FROM jobs ORDER BY rowid')]
        return revision, jobs

    def get(self, job_id):
        with self.database.connection() as connection:
            row = connection.execute('SELECT payload FROM jobs WHERE id=?', (job_id,)).fetchone()
        if row is None:
            raise ApiException(404, 'not_found', 'Download job not found')
        return JobResponse.model_validate_json(row[0])

    def update(self, job_id, expected_status=None, **changes):
        with self.database.connection() as connection:
            connection.execute('BEGIN IMMEDIATE')
            row = connection.execute('SELECT payload FROM jobs WHERE id=?', (job_id,)).fetchone()
            if row is None:
                raise ApiException(404, 'not_found', 'Download job not found')
            job = JobResponse.model_validate_json(row[0])
            if expected_status is not None and job.status != expected_status:
                return job
            for name, value in changes.items():
                setattr(job, name, value)
            self._save(connection, job)
        return job

    def claim(self):
        with self.database.connection() as connection:
            connection.execute('BEGIN IMMEDIATE')
            row = connection.execute("SELECT payload FROM jobs WHERE status='queued' ORDER BY rowid LIMIT 1").fetchone()
            if row is None:
                return None
            job = JobResponse.model_validate_json(row[0])
            job.status = 'downloading'
            return self._save(connection, job)

    def recover(self):
        with self.database.connection() as connection:
            connection.execute('BEGIN IMMEDIATE')
            rows = connection.execute("SELECT payload FROM jobs WHERE status='downloading'").fetchall()
            for row in rows:
                job = JobResponse.model_validate_json(row[0])
                job.status = 'queued'
                job.progress = JobProgress()
                job.error = None
                self._save(connection, job)

    def action(self, job_id, action):
        transitions = {
            'pause': ({'queued', 'downloading'}, 'paused'),
            'resume': ({'paused'}, 'queued'),
            'cancel': ({'queued', 'downloading', 'paused'}, 'canceled'),
            'retry': ({'failed', 'canceled'}, 'queued'),
        }
        with self.database.connection() as connection:
            connection.execute('BEGIN IMMEDIATE')
            row = connection.execute('SELECT payload FROM jobs WHERE id=?', (job_id,)).fetchone()
            if row is None:
                raise ApiException(404, 'not_found', 'Download job not found')
            job = JobResponse.model_validate_json(row[0])
            allowed, target = transitions[action]
            if job.status not in allowed:
                raise ApiException(409, 'invalid_job_state', 'This action is unavailable for the current download state')
            job.status = target
            job.error = None
            job.progress = job.progress.model_copy(update={'speed_bytes_per_second': None, 'eta_seconds': None})
            if action == 'retry':
                job.progress = JobProgress()
                job.output_name = None
            return self._save(connection, job)

    def remove(self, job_id):
        with self.database.connection() as connection:
            connection.execute('BEGIN IMMEDIATE')
            row = connection.execute('SELECT status FROM jobs WHERE id=?', (job_id,)).fetchone()
            if row is None:
                raise ApiException(404, 'not_found', 'Download job not found')
            if row[0] not in {'complete', 'failed', 'canceled'}:
                raise ApiException(409, 'invalid_job_state', 'Cancel the download before removing it')
            connection.execute('DELETE FROM jobs WHERE id=?', (job_id,))
            connection.execute('UPDATE queue_revision SET value=value+1 WHERE id=1')
