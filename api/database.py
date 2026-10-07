"""Short-lived SQLite connections and ordered, atomic startup migrations."""

import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from collections.abc import Iterator


@dataclass(frozen=True)
class Migration:
    version: int
    name: str
    statements: tuple[str, ...]


# Append migrations; never edit migrations already shipped. Job tables belong
# to the persistent queue milestone. The baseline establishes the version ledger.
MIGRATIONS = (
    Migration(1, "baseline", (
        """CREATE TABLE schema_migrations (
            version INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            applied_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
        )""",
    )),
)


class Database:
    def __init__(self, path: Path):
        self.path = path

    @contextmanager
    def connection(self) -> Iterator[sqlite3.Connection]:
        """Commit on success, roll back on failure, and always close.

        Each request or worker opens its own connection in the thread using it.
        SQLite's default thread guard remains enabled.
        """
        connection = sqlite3.connect(self.path, timeout=5)
        try:
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA foreign_keys = ON")
            connection.execute("PRAGMA synchronous = FULL")
            with connection:
                yield connection
        finally:
            connection.close()

    def initialize(self, migrations: tuple[Migration, ...] = MIGRATIONS) -> None:
        if [migration.version for migration in migrations] != list(range(1, len(migrations) + 1)):
            raise ValueError("Migration versions must be consecutive and start at 1")
        with self.connection() as connection:
            # WAL allows readers while a worker writes. Reserve the writer lock
            # before inspecting versions so concurrent startups cannot race.
            mode = connection.execute("PRAGMA journal_mode = WAL").fetchone()[0]
            if mode != "wal":
                raise RuntimeError("SQLite WAL mode could not be enabled")
            connection.execute("BEGIN IMMEDIATE")
            exists = connection.execute(
                "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'schema_migrations'"
            ).fetchone()
            applied = connection.execute(
                "SELECT version, name FROM schema_migrations ORDER BY version"
            ).fetchall() if exists else []
            expected = [(migration.version, migration.name) for migration in migrations]
            if [tuple(row) for row in applied] != expected[:len(applied)] or len(applied) > len(expected):
                raise RuntimeError("Database migration history is incompatible with this application")
            for migration in migrations[len(applied):]:
                # executescript() implicitly commits; individual execute() calls
                # preserve the transaction across both DDL and version updates.
                for statement in migration.statements:
                    connection.execute(statement)
                connection.execute(
                    "INSERT INTO schema_migrations (version, name) VALUES (?, ?)",
                    (migration.version, migration.name),
                )
