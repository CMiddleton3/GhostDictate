# Project Guidelines

## Code Style

- Follow the existing Python style: type hints, `pathlib.Path`, and focused classes and functions.
- Keep user-facing errors actionable and preserve diagnostic logging.
- Avoid adding dependencies unless the project requirements need them.

## Architecture

- `ui.py` owns the PySide6 interface; `recorder.py` handles microphone capture; `transcriber.py` wraps the local Cactus Whistle model; `settings.py` persists user preferences.
- Keep recording and transcription work off the UI thread, and preserve temporary-audio cleanup.
- The app transcribes locally. Preserve its telemetry opt-outs and offline behavior when the model and runtime are cached.

## Build and Test

- Run tests with `.\.venv\Scripts\python.exe -m unittest discover -s tests -v`.
- Build the Windows executable with `.\.venv\Scripts\python.exe build_windows.py`.
- See [README.md](README.md) for environment setup, usage, and packaging details.

## Conventions

- Keep changes focused and update the related tests when behavior changes.
- Preserve compatibility with Windows and the Python versions supported by the project.
