from __future__ import annotations

import json
import logging
import os
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from settings import AppSettings


LOGGER = logging.getLogger(__name__)
CONFIG_NAME = "ghostdictate.json"


@dataclass(frozen=True)
class TranscriptionResult:
    text: str
    language: str
    elapsed_seconds: float
    model_info: str


class NeedleTranscriber:
    """Loads and reuses Cactus Whistle on the calling thread."""

    def __init__(self) -> None:
        self._model: Any | None = None
        self._model_key: str | None = None

    def _load_model(self, model_path: str | None) -> Any:
        os.environ["NEEDLE_TELEMETRY"] = "0"
        os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"

        try:
            import needle
            from needle.agent import fetch
        except ImportError as exc:
            raise RuntimeError(
                "Cactus Needle is not installed. Run "
                "'python -m pip install -r requirements.txt'."
            ) from exc

        distribution_directory = self._distribution_directory()
        configured_model, configured_engine = self._configured_resources(
            distribution_directory
        )
        local_engine = configured_engine or (
            distribution_directory / fetch.lib_name(3)
        )
        if local_engine.is_file():
            os.environ[fetch.lib_path_env(3)] = str(local_engine)

        if model_path:
            resolved_path = Path(model_path).expanduser().resolve()
            if not resolved_path.is_file():
                raise FileNotFoundError(
                    f"The selected Whistle model does not exist: {resolved_path}"
                )
            model_key = str(resolved_path)
        elif configured_model is not None:
                model_key = str(configured_model)
        else:
                local_model = distribution_directory / fetch.base_weights(fetch.WHISTLE)
                model_key = str(local_model) if local_model.is_file() else None

        if self._model is not None and self._model_key == model_key:
            return self._model

        if self._cached_runtime_available(needle, fetch, model_key):
            os.environ["HF_HUB_OFFLINE"] = "1"
            LOGGER.info("Whistle model and runtime are available locally; enforcing offline mode")

        try:
            model = needle.Whistle(weights=model_key)
        except Exception as exc:
            LOGGER.exception("Could not load the Whistle speech model")
            raise RuntimeError(
                "Whistle could not load its model. On first use, connect to the "
                "internet to download the model and runtime. Once cached, the app "
                "runs in offline mode. "
                f"Details: {exc}"
            ) from exc

        self._model = model
        self._model_key = model_key
        LOGGER.info("Whistle model loaded from %s", model.weights)
        return model

    @staticmethod
    def _distribution_directory() -> Path:
        if getattr(sys, "frozen", False):
            return Path(sys.executable).resolve().parent
        return Path(__file__).resolve().parent

    @staticmethod
    def _configured_resources(directory: Path) -> tuple[Path | None, Path | None]:
        config_path = directory / CONFIG_NAME
        if not config_path.is_file():
            source_library = directory / "assets" / "lib"
            source_model = source_library / "whistle.cact"
            source_engine = source_library / "libneedle.dll"
            return (
                source_model if source_model.is_file() else None,
                source_engine if source_engine.is_file() else None,
            )

        try:
            data = json.loads(config_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise RuntimeError(
                f"Could not read the app configuration {config_path}: {exc}"
            ) from exc
        if not isinstance(data, dict):
            raise RuntimeError(f"The app configuration {config_path} must be a JSON object.")

        paths: list[Path] = []
        for key in ("model_path", "runtime_path"):
            value = data.get(key)
            if not isinstance(value, str) or not value.strip():
                raise RuntimeError(
                    f"The app configuration {config_path} must specify '{key}'."
                )
            path = Path(value).expanduser()
            if not path.is_absolute():
                path = directory / path
            path = path.resolve()
            if not path.is_file():
                raise FileNotFoundError(
                    f"The configured {key.replace('_path', '')} file was not found: {path}"
                )
            paths.append(path)

        return paths[0], paths[1]

    @staticmethod
    def _cached_runtime_available(needle: Any, fetch: Any, model_key: str | None) -> bool:
        if model_key is None:
            model_path = (
                Path(fetch.cache_dir(fetch.WHISTLE))
                / fetch.base_weights(fetch.WHISTLE)
            )
        else:
            model_path = Path(model_key)

        engine_cache = Path(fetch.cache_dir(3))
        engine_path = engine_cache / fetch.lib_name(3)
        bundled_engine_path = Path(needle.__file__).resolve().parent / fetch.lib_name(3)
        configured_engine = os.environ.get(fetch.lib_path_env(3))
        return model_path.is_file() and (
            engine_path.is_file()
            or bundled_engine_path.is_file()
            or (configured_engine is not None and Path(configured_engine).is_file())
        )

    def transcribe(
        self,
        audio_path: Path,
        settings: AppSettings,
    ) -> TranscriptionResult:
        model = self._load_model(settings.model_path)
        language = None if settings.auto_detect_language else settings.language

        started = time.perf_counter()
        try:
            result = model.transcribe(str(audio_path), language=language)
        except Exception as exc:
            LOGGER.exception("Whistle transcription failed")
            raise RuntimeError(f"Transcription failed: {exc}") from exc
        elapsed = time.perf_counter() - started

        if not isinstance(result, dict) or not isinstance(result.get("text"), str):
            raise RuntimeError("Whistle returned an unexpected transcription result.")

        return TranscriptionResult(
            text=result["text"].strip(),
            language=str(result.get("language") or "unknown"),
            elapsed_seconds=elapsed,
            model_info=str(Path(model.weights).resolve()),
        )
