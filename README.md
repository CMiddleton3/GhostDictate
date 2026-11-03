# GhostDictate

A Windows 11 desktop app for recording microphone audio and transcribing it locally with Cactus Compute's Whistle model through the `cactus-needle` Python package. Audio is recorded as 16 kHz mono WAV, transcribed on-device, and the temporary WAV is removed automatically.

The app does not use cloud transcription or OpenAI APIs. Needle's telemetry is disabled by the app. On first use, Needle downloads the Whistle model and its native runtime from its model repository. Once both are cached, the app automatically enables Hugging Face offline mode before loading Whistle, so subsequent launches do not check for model updates or contact the model host. The app does not automatically update itself or its Python packages. If you already have a `.cact` Whistle model, select it in the settings panel to skip the default model download.

## Project structure

```text
OnPerm-Transcribe/
├── assets/
│   ├── app_icon.svg
│   └── lib/
│       ├── libneedle.dll
│       └── whistle.cact
├── build_windows.py
├── main.py
├── recorder.py
├── requirements.txt
├── settings.py
├── transcriber.py
├── ui.py
├── tests/
│   ├── test_recorder.py
│   ├── test_settings.py
│   └── test_transcriber.py
└── README.md
```

## Requirements

- Windows 11
- Python 3.10 or newer (64-bit recommended)
- A microphone

## Install and run

Open PowerShell in this folder:

```powershell
py -3.10 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python main.py
```

The checked-in `assets\lib` folder contains the Whistle model and native runtime used by this project. They are copied into `dist\lib` during builds, so building and running this version does not require downloading either file. The app automatically uses offline mode when both local files are available.

## Offline Python dependencies

The `vendor\` folder contains wheels for the requirements and their transitive dependencies. They were downloaded for 64-bit Windows and CPython 3.14. To install from this folder without reaching a package index:

```powershell
python -m pip install --no-index --find-links .\vendor -r requirements.txt
```

Some wheels contain Python-version-specific native binaries. For another Python version or platform, download a matching wheel set.

When Windows asks for microphone access, allow it for the app. If no microphone is detected, check **Settings > Privacy & security > Microphone** and confirm that desktop apps are permitted.

## Use

- Click the large microphone button to start recording, then click it again to stop and transcribe.
- Use **Start New Recording** to record another note; completed text is appended to the editable transcript.
- Choose automatic language detection or one of Whistle's supported languages: English, German, French, Spanish, Italian, Dutch, and Polish.
- Copy, clear, or save the transcript as a UTF-8 text file with the buttons below the editor.
- Choose a custom Whistle `.cact` model and toggle dark mode in the settings panel.

Settings are stored locally under `%APPDATA%\GhostDictate\settings.json`. Application logs are stored under `%LOCALAPPDATA%\GhostDictate\logs\app.log`.

## Build a single-file Windows executable

Install the requirements in the active virtual environment, then run:

```powershell
python build_windows.py
```

The build script generates `assets\app_icon.ico` if needed and invokes this equivalent PyInstaller command:

```powershell
python -m PyInstaller --noconfirm --clean --onefile --windowed --name "GhostDictate" --icon "assets\app_icon.ico" --add-data "assets\app_icon.svg;assets" --collect-all needle --hidden-import PySide6.QtSvg main.py
```

The executable is written to `dist\GhostDictate.exe`. The build script copies the model and runtime from `assets\lib` into `dist\lib\` and creates `dist\ghostdictate.json` with their relative paths. Keep the EXE, configuration file, and `lib` folder together when archiving or redeploying the app. Build the executable on Windows with the same Python architecture as the intended machine.

## Create an Inno Setup installer

Install Inno Setup 6, build the executable and distribution files as described above, then compile the installer script:

```powershell
& "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe" .\installer.iss
```

The installer is written to `dist\GhostDictate-Setup.exe`. It installs GhostDictate for the current user, includes the model and native runtime, and offers an optional desktop shortcut.

Run the local tests with:

```powershell
python -m unittest discover -s tests -v
```

## Needle API integration

The app uses the current Python API documented by Cactus Compute:

```python
import needle

whistle = needle.Whistle()  # or needle.Whistle(weights="path/to/model.cact")
result = whistle.transcribe("recording.wav", language=None)
print(result["text"])
```

Setting `language=None` enables language detection. A supported language code (for example, `"en"`) forces a language. The returned mapping includes the transcript and detected language. The app creates one `needle.Whistle` instance and uses it from its dedicated worker thread.
