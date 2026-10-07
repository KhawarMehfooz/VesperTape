import unittest

from pydantic import ValidationError

from api.contracts import CreateJobRequest, JobProgress, PreviewItem
from scripts.generate_api_types import generate


class ContractTests(unittest.TestCase):
    def test_minimal_job_uses_server_defaults(self):
        job = CreateJobRequest.model_validate({"url": "https://example.com/video"})
        self.assertEqual(job.settings.mode, "video")
        self.assertEqual(job.selection.item_indices, [])
        self.assertEqual(job.settings.destination, "default")

    def test_unknown_fields_and_unsupported_mode_are_rejected(self):
        for payload in (
            {"url": "https://example.com", "command": "anything"},
            {"url": "https://example.com", "settings": {"mode": "invalid"}},
            {"url": ""},
        ):
            with self.subTest(payload=payload), self.assertRaises(ValidationError):
                CreateJobRequest.model_validate(payload)

    def test_unavailable_metadata_is_preserved_as_null(self):
        item = PreviewItem(id="video", url="https://example.com", title="Video")
        self.assertIsNone(item.model_dump()["duration_seconds"])
        self.assertEqual(item.formats, [])

    def test_progress_bounds(self):
        for payload in ({"percent": 101}, {"downloaded_bytes": -1}, {"eta_seconds": -1}):
            with self.subTest(payload=payload), self.assertRaises(ValidationError):
                JobProgress.model_validate(payload)

    def test_generated_types_distinguish_inputs_from_responses(self):
        types = generate()
        self.assertIn("settings?: DownloadSettings;", types)
        self.assertIn("duration_seconds: number | null;", types)
        self.assertIn("export type DownloadSettingsInput = Partial<DownloadSettings>;", types)


if __name__ == "__main__":
    unittest.main()
