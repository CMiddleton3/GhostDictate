from __future__ import annotations

import sys
import tempfile
import types
import unittest
import wave
from pathlib import Path
from unittest.mock import patch

import numpy as np

from recorder import AudioCaptureError, AudioRecorder, SAMPLE_RATE


class AudioRecorderTests(unittest.TestCase):
    def test_missing_microphone_has_a_friendly_error(self) -> None:
        class FakePortAudioError(Exception):
            pass

        fake_sounddevice = types.ModuleType("sounddevice")
        fake_sounddevice.PortAudioError = FakePortAudioError

        def no_input_device(**_kwargs):
            raise FakePortAudioError("no input")

        fake_sounddevice.query_devices = no_input_device

        with patch.dict(sys.modules, {"sounddevice": fake_sounddevice}):
            with self.assertRaisesRegex(AudioCaptureError, "No microphone was found"):
                AudioRecorder().start()

    def test_writes_mono_16khz_temporary_wave_file(self) -> None:
        class FakePortAudioError(Exception):
            pass

        class FakeStream:
            def __init__(self, *, callback, **_kwargs) -> None:
                self.callback = callback

            def start(self) -> None:
                self.callback(np.array([[0.25], [-0.25]], dtype=np.float32), 2, None, None)

            def stop(self) -> None:
                pass

            def close(self) -> None:
                pass

        fake_sounddevice = types.ModuleType("sounddevice")
        fake_sounddevice.PortAudioError = FakePortAudioError
        fake_sounddevice.query_devices = lambda **_kwargs: {"max_input_channels": 1}
        fake_sounddevice.InputStream = FakeStream

        with patch.dict(sys.modules, {"sounddevice": fake_sounddevice}):
            recorder = AudioRecorder()
            recorder.start()
            audio_path = recorder.stop()

        try:
            with wave.open(str(audio_path), "rb") as wav_file:
                self.assertEqual(wav_file.getnchannels(), 1)
                self.assertEqual(wav_file.getframerate(), SAMPLE_RATE)
                self.assertEqual(wav_file.getsampwidth(), 2)
                self.assertEqual(wav_file.getnframes(), 2)
        finally:
            Path(audio_path).unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
