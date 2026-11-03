from __future__ import annotations

import json
import os
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

from settings import AppSettings
from transcriber import NeedleTranscriber


class NeedleTranscriberTests(unittest.TestCase):
    def test_source_assets_are_used_when_no_distribution_config_exists(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            library_directory = root / "assets" / "lib"
            library_directory.mkdir(parents=True)
            model_path = library_directory / "whistle.cact"
            runtime_path = library_directory / "libneedle.dll"
            model_path.touch()
            runtime_path.touch()

            model, runtime = NeedleTranscriber._configured_resources(root)

            self.assertEqual(model, model_path)
            self.assertEqual(runtime, runtime_path)

    def test_reads_relative_model_and_runtime_paths_from_config(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            library_directory = root / "lib"
            library_directory.mkdir()
            model_path = library_directory / "whistle.cact"
            runtime_path = library_directory / "libneedle.dll"
            model_path.touch()
            runtime_path.touch()
            (root / "ghostdictate.json").write_text(
                json.dumps(
                    {
                        "model_path": "lib/whistle.cact",
                        "runtime_path": "lib/libneedle.dll",
                    }
                ),
                encoding="utf-8",
            )

            model, runtime = NeedleTranscriber._configured_resources(root)

            self.assertEqual(model, model_path.resolve())
            self.assertEqual(runtime, runtime_path.resolve())

    def test_uses_whistle_instance_api_and_auto_detection(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            model_path = Path(temporary_directory) / "whistle.cact"
            audio_path = Path(temporary_directory) / "recording.wav"
            model_path.touch()
            audio_path.touch()
            calls: list[tuple[str, str | None]] = []

            class FakeWhistle:
                def __init__(self, weights: str | None = None) -> None:
                    self.weights = weights or str(model_path)

                def transcribe(
                    self,
                    audio: str,
                    language: str | None = None,
                ) -> dict[str, str]:
                    calls.append((audio, language))
                    return {"text": "  local transcript  ", "language": "en"}

            fake_needle = types.ModuleType("needle")
            fake_needle.Whistle = FakeWhistle
            fake_agent = types.ModuleType("needle.agent")
            fake_agent.fetch = types.SimpleNamespace(
                WHISTLE="whistle",
                lib_name=lambda _engine: "libneedle.dll",
                lib_path_env=lambda _engine: "NEEDLE3_LIB_PATH",
                base_weights=lambda _engine: "whistle.cact",
            )
            with (
                patch.dict(
                    sys.modules,
                    {"needle": fake_needle, "needle.agent": fake_agent},
                ),
                patch.object(
                    NeedleTranscriber,
                    "_cached_runtime_available",
                    return_value=False,
                ),
                patch.object(
                    NeedleTranscriber,
                    "_distribution_directory",
                    return_value=Path(temporary_directory),
                ),
            ):
                settings = AppSettings(auto_detect_language=True)
                result = NeedleTranscriber().transcribe(audio_path, settings)

            self.assertEqual(result.text, "local transcript")
            self.assertEqual(result.language, "en")
            self.assertEqual(result.model_info, str(model_path.resolve()))
            self.assertEqual(calls, [(str(audio_path), None)])

    def test_disables_needle_telemetry(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            model_path = Path(temporary_directory) / "whistle.cact"
            audio_path = Path(temporary_directory) / "recording.wav"
            model_path.touch()
            audio_path.touch()

            class FakeWhistle:
                def __init__(self, weights: str | None = None) -> None:
                    self.weights = weights or str(model_path)

                def transcribe(self, _audio: str, language: str | None = None):
                    return {"text": "offline", "language": language or "en"}

            fake_needle = types.ModuleType("needle")
            fake_needle.Whistle = FakeWhistle
            fake_agent = types.ModuleType("needle.agent")
            fake_agent.fetch = types.SimpleNamespace(
                WHISTLE="whistle",
                lib_name=lambda _engine: "libneedle.dll",
                lib_path_env=lambda _engine: "NEEDLE3_LIB_PATH",
                base_weights=lambda _engine: "whistle.cact",
            )
            with (
                patch.dict(
                    sys.modules,
                    {"needle": fake_needle, "needle.agent": fake_agent},
                ),
                patch.dict(os.environ, {"NEEDLE_TELEMETRY": "1"}),
                patch.object(
                    NeedleTranscriber,
                    "_cached_runtime_available",
                    return_value=False,
                ),
            ):
                NeedleTranscriber().transcribe(audio_path, AppSettings())
                self.assertEqual(os.environ["NEEDLE_TELEMETRY"], "0")

    def test_cached_model_and_runtime_enforce_hub_offline_mode(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            model_path = root / "whistle.cact"
            runtime_path = root / "runtime"
            package_path = root / "needle"
            model_path.touch()
            package_path.mkdir()
            (runtime_path / "libneedle.dll").parent.mkdir(parents=True)
            (runtime_path / "libneedle.dll").touch()

            class FakeFetch:
                WHISTLE = "whistle"

                @staticmethod
                def cache_dir(engine) -> str:
                    return str(runtime_path if engine == 3 else root)

                @staticmethod
                def base_weights(_engine) -> str:
                    return model_path.name

                @staticmethod
                def lib_name(_engine) -> str:
                    return "libneedle.dll"

                @staticmethod
                def lib_path_env(_engine) -> str:
                    return "NEEDLE3_LIB_PATH"

            class FakeWhistle:
                def __init__(self, weights: str | None = None) -> None:
                    self.weights = weights or str(model_path)

            fake_needle = types.ModuleType("needle")
            fake_needle.__file__ = str(package_path / "__init__.py")
            fake_needle.Whistle = FakeWhistle
            fake_agent = types.ModuleType("needle.agent")
            fake_agent.fetch = FakeFetch
            with (
                patch.dict(
                    sys.modules,
                    {"needle": fake_needle, "needle.agent": fake_agent},
                ),
                patch.dict(os.environ, {"HF_HUB_OFFLINE": "0"}),
            ):
                NeedleTranscriber()._load_model(None)
                self.assertEqual(os.environ["HF_HUB_OFFLINE"], "1")


if __name__ == "__main__":
    unittest.main()
