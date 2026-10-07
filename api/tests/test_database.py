import sqlite3
import tempfile
import unittest
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

from api.database import Database, MIGRATIONS, Migration


class DatabaseTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.database = Database(Path(self.directory.name) / "test.sqlite3")

    def test_initialization_is_persistent_and_repeatable(self):
        self.database.initialize()
        Database(self.database.path).initialize()
        with self.database.connection() as connection:
            self.assertEqual(connection.execute("PRAGMA journal_mode").fetchone()[0], "wal")
            self.assertEqual(connection.execute("PRAGMA foreign_keys").fetchone()[0], 1)
            rows = connection.execute("SELECT * FROM schema_migrations").fetchall()
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["version"], 1)
            self.assertTrue(rows[0]["applied_at"].endswith("Z"))
        with self.assertRaises(sqlite3.ProgrammingError):
            connection.execute("SELECT 1")

    def test_upgrade_and_failed_migration_roll_back(self):
        self.database.initialize()
        upgrade = Migration(2, "example", ("CREATE TABLE example (id INTEGER PRIMARY KEY)",))
        self.database.initialize(MIGRATIONS + (upgrade,))
        broken = Migration(3, "broken", (
            "CREATE TABLE partial (id INTEGER)",
            "INSERT INTO nonexistent VALUES (1)",
        ))
        with self.assertRaises(sqlite3.OperationalError):
            self.database.initialize(MIGRATIONS + (upgrade, broken))
        with self.database.connection() as connection:
            self.assertEqual(connection.execute("SELECT MAX(version) FROM schema_migrations").fetchone()[0], 2)
            self.assertIsNone(connection.execute("SELECT name FROM sqlite_master WHERE name='partial'").fetchone())
        with self.assertRaises(RuntimeError):
            self.database.initialize()

    def test_connection_rolls_back_failed_writes(self):
        self.database.initialize()
        with self.assertRaises(RuntimeError):
            with self.database.connection() as connection:
                connection.execute("INSERT INTO schema_migrations (version, name) VALUES (2, 'test')")
                raise RuntimeError("abort")
        with self.database.connection() as connection:
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM schema_migrations").fetchone()[0], 1)

    def test_concurrent_startups_apply_upgrade_once(self):
        self.database.initialize()
        upgrade = Migration(2, "example", ("CREATE TABLE example (id INTEGER PRIMARY KEY)",))
        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [executor.submit(self.database.initialize, MIGRATIONS + (upgrade,)) for _ in range(2)]
            for future in futures:
                future.result()
        with self.database.connection() as connection:
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM schema_migrations").fetchone()[0], 2)


if __name__ == "__main__":
    unittest.main()
