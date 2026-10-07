import tempfile
import unittest
import asyncio
from pathlib import Path
from unittest.mock import patch

from api.settings import AppSettings


class SettingsTests(unittest.TestCase):
    def test_defaults_and_derived_download_path(self):
        settings = AppSettings.from_env({})
        self.assertEqual(settings.data_dir, Path("data").resolve())
        self.assertEqual(settings.download_dir, settings.data_dir / "downloads")
        self.assertEqual(settings.worker_count, 1)

    def test_environment_overrides_and_public_defaults(self):
        settings = AppSettings.from_env({
            "VESPERTAPE_DATA_DIR": "/tmp/vespertape-data",
            "VESPERTAPE_DOWNLOAD_DIR": "/tmp/vespertape-media",
            "VESPERTAPE_WORKER_COUNT": "2",
            "VESPERTAPE_ALLOWED_MODES": '["audio"]',
            "VESPERTAPE_ALLOWED_QUALITIES": '["720p"]',
            "VESPERTAPE_ALLOWED_FORMATS": '["mp3", "m4a"]',
        })
        public = settings.public_settings().model_dump()
        self.assertEqual(settings.download_dir, Path("/tmp/vespertape-media").resolve())
        self.assertEqual(public["worker_count"], 2)
        self.assertEqual(public["defaults"]["mode"], "audio")
        self.assertEqual(public["defaults"]["format"], "mp3")
        self.assertEqual(public["destinations"], ["default"])
        self.assertNotIn("data_dir", public)
        self.assertNotIn("download_dir", public)

    def test_invalid_configuration_fails(self):
        for key, value in (
            ("WORKER_COUNT", "0"), ("WORKER_COUNT", "1.5"),
            ("DATA_DIR", ""), ("DOWNLOAD_DIR", " "),
            ("ALLOWED_FORMATS", '["unsupported"]'),
            ("ALLOWED_MODES", "[]"), ("ALLOWED_MODES", '["audio", "audio"]'),
            ("ALLOWED_QUALITIES", '"best"'), ("ALLOWED_FORMATS", "auto,mp4"),
        ):
            with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                AppSettings.from_env({f"VESPERTAPE_{key}": value})

    def test_prepare_storage_and_reject_file_as_directory(self):
        with tempfile.TemporaryDirectory() as root:
            settings = AppSettings(data_dir=Path(root) / "data")
            settings.prepare_directories()
            self.assertTrue(settings.download_dir.is_dir())
            file = Path(root) / "file"
            file.write_text("occupied")
            with self.assertRaises(OSError):
                AppSettings(data_dir=file).prepare_directories()

    def test_api_startup_loads_configuration(self):
        from api.main import app, get_settings

        async def start():
            async with app.router.lifespan_context(app):
                self.assertTrue(app.state.settings.download_dir.is_dir())
                self.assertEqual(get_settings().worker_count, 3)
                self.assertEqual(app.state.database.path, Path(root).resolve() / "vespertape.sqlite3")
                with app.state.database.connection() as connection:
                    self.assertEqual(connection.execute("SELECT MAX(version) FROM schema_migrations").fetchone()[0], 2)

        with tempfile.TemporaryDirectory() as root, patch.dict(
            "os.environ",
            {"VESPERTAPE_DATA_DIR": root, "VESPERTAPE_WORKER_COUNT": "3"},
            clear=True,
        ):
            asyncio.run(start())


if __name__ == "__main__":
    unittest.main()
