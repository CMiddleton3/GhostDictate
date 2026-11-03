from __future__ import annotations

import logging
import tempfile
import threading
import wave
from pathlib import Path
from typing import Any


LOGGER = logging.getLogger(__name__)
SAMPLE_RATE = 16_000


class AudioCaptureError(RuntimeError):
    """An audio input device could not be opened or recorded."""


class AudioRecorder:
    """Captures mono microphone audio and writes a temporary 16 kHz WAV file."""

    def __init__(self) -> None:
        self._stream: Any | None = None
        self._chunks: list[Any] = []
        self._lock = threading.Lock()

    @property
    def is_recording(self) -> bool:
        return self._stream is not None

    def start(self) -> None:
        try:
            import sounddevice as sd
        except ImportError as exc:
            raise AudioCaptureError(
                "The audio capture dependency is missing. Reinstall the app "
                "with its requirements."
            ) from exc

        try:
            device = sd.query_devices(kind="input")
        except sd.PortAudioError as exc:
            raise AudioCaptureError(
                "No microphone was found. Connect a microphone and check "
                "Windows microphone permissions."
            ) from exc

        if device["max_input_channels"] < 1:
            raise AudioCaptureError(
                "No microphone input is available. Connect a microphone and "
                "check Windows microphone permissions."
            )

        if self._stream is not None:
            raise AudioCaptureError("A recording is already in progress.")

        with self._lock:
            self._chunks = []

        stream: Any | None = None
        try:
            stream = sd.InputStream(
                samplerate=SAMPLE_RATE,
                channels=1,
                dtype="float32",
                callback=self._on_audio,
            )
            stream.start()
        except sd.PortAudioError as exc:
            if stream is not None:
                try:
                    stream.close()
                except Exception:
                    LOGGER.exception("Could not close the failed microphone stream")
            raise AudioCaptureError(
                "Could not start microphone recording. Check that the device "
                "is not being used exclusively by another app."
            ) from exc

        self._stream = stream
        LOGGER.info("Microphone recording started at %d Hz", SAMPLE_RATE)

    def _on_audio(
        self,
        indata: Any,
        _frames: int,
        _time_info: Any,
        status: Any,
    ) -> None:
        if status:
            LOGGER.warning("Audio input status: %s", status)
        with self._lock:
            self._chunks.append(indata.copy())

    def stop(self) -> Path:
        stream = self._stream
        if stream is None:
            raise AudioCaptureError("There is no recording to stop.")

        self._stream = None
        try:
            stream.stop()
        except Exception as exc:
            try:
                stream.close()
            except Exception:
                LOGGER.exception("Could not close the microphone after a stop failure")
            raise AudioCaptureError(f"Could not stop microphone recording: {exc}") from exc
        try:
            stream.close()
        except Exception as exc:
            raise AudioCaptureError(f"Could not close the microphone: {exc}") from exc

        with self._lock:
            chunks, self._chunks = self._chunks, []

        if not chunks:
            raise AudioCaptureError("No audio was captured. Please try recording again.")

        try:
            import numpy as np
        except ImportError as exc:
            raise AudioCaptureError(
                "The audio processing dependency is missing. Reinstall the app "
                "with its requirements."
            ) from exc

        try:
            samples = np.concatenate(chunks, axis=0).reshape(-1)
        except ValueError as exc:
            raise AudioCaptureError(f"Could not combine recorded audio: {exc}") from exc
        if samples.size == 0:
            raise AudioCaptureError("No audio was captured. Please try recording again.")

        pcm_samples = np.clip(samples * 32767.0, -32768, 32767).astype("<i2")
        try:
            temporary = tempfile.NamedTemporaryFile(
                prefix="needle_voice_",
                suffix=".wav",
                delete=False,
            )
            temporary_path = Path(temporary.name)
            temporary.close()
        except OSError as exc:
            raise AudioCaptureError(
                f"Could not create a temporary recording file: {exc}"
            ) from exc

        try:
            with wave.open(str(temporary_path), "wb") as wav_file:
                wav_file.setnchannels(1)
                wav_file.setsampwidth(2)
                wav_file.setframerate(SAMPLE_RATE)
                wav_file.writeframes(pcm_samples.tobytes())
        except (OSError, wave.Error) as exc:
            temporary_path.unlink(missing_ok=True)
            raise AudioCaptureError(
                f"Could not write the temporary recording: {exc}"
            ) from exc

        LOGGER.info("Microphone recording stopped; temporary audio is ready")
        return temporary_path
