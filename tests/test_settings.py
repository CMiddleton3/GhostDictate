from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from settings import AppSettings


class AppSettingsTests(unittest.TestCase):
    def test_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "settings.json"
            original = AppSettings(
                auto_detect_language=False,
                language="fr",
                model_path="C:/models/whistle.cact",
                dark_mode=False,
            )

            original.save(path)

            self.assertEqual(AppSettings.load(path), original)

    def test_missing_settings_use_defaults(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            settings = AppSettings.load(Path(temporary_directory) / "missing.json")

        self.assertEqual(settings, AppSettings())


if __name__ == "__main__":
    unittest.main()
