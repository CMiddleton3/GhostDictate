from __future__ import annotations

import json
import logging
import os
from dataclasses import asdict, dataclass
from pathlib import Path


LOGGER = logging.getLogger(__name__)
LANGUAGES: tuple[tuple[str, str], ...] = (
    ("English", "en"),
    ("German", "de"),
    ("French", "fr"),
    ("Spanish", "es"),
    ("Italian", "it"),
    ("Dutch", "nl"),
    ("Polish", "pl"),
)
LANGUAGE_CODES = {code for _, code in LANGUAGES}


def settings_file() -> Path:
    app_data = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    return app_data / "GhostDictate" / "settings.json"


@dataclass
class AppSettings:
    auto_detect_language: bool = True
    language: str = "en"
    model_path: str | None = None
    dark_mode: bool = True

    @classmethod
    def load(cls, path: Path | None = None) -> AppSettings:
        file_path = path or settings_file()
        try:
            data = json.loads(file_path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return cls()
        except (OSError, json.JSONDecodeError) as exc:
            LOGGER.warning("Could not read settings from %s: %s", file_path, exc)
            return cls()

        if not isinstance(data, dict):
            LOGGER.warning("Settings file %s does not contain a JSON object", file_path)
            return cls()

        language = data.get("language", "en")
        model_path = data.get("model_path")
        if not isinstance(language, str) or language not in LANGUAGE_CODES:
            LOGGER.warning("Unsupported language in %s; using English", file_path)
            language = "en"
        if model_path is not None and not isinstance(model_path, str):
            LOGGER.warning("Invalid model path in %s; using the default model", file_path)
            model_path = None

        return cls(
            auto_detect_language=data.get("auto_detect_language", True) is True,
            language=language,
            model_path=model_path or None,
            dark_mode=data.get("dark_mode", True) is True,
        )

    def save(self, path: Path | None = None) -> None:
        file_path = path or settings_file()
        file_path.parent.mkdir(parents=True, exist_ok=True)
        temporary_path = file_path.with_suffix(".json.tmp")
        temporary_path.write_text(
            json.dumps(asdict(self), indent=2),
            encoding="utf-8",
        )
        temporary_path.replace(file_path)
