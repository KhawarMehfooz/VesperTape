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

    def update(self, job_id, **changes):
        with self.database.connection() as connection:
            connection.execute('BEGIN IMMEDIATE')
            row = connection.execute('SELECT payload FROM jobs WHERE id=?', (job_id,)).fetchone()
            job = JobResponse.model_validate_json(row[0])
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
