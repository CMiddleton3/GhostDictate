from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from shutil import copy2


ROOT = Path(__file__).resolve().parent
ASSETS = ROOT / "assets"
SOURCE_LIB_DIRECTORY = ASSETS / "lib"
ICON_PATH = ASSETS / "app_icon.ico"
SVG_PATH = ASSETS / "app_icon.svg"
DIST_DIRECTORY = ROOT / "dist"
LIB_DIRECTORY = DIST_DIRECTORY / "lib"
MODEL_BACKUP_NAME = "whistle.cact"
ENGINE_BACKUP_NAME = "libneedle.dll"
CONFIG_NAME = "ghostdictate.json"


def create_icon() -> None:
    if ICON_PATH.is_file():
        return

    try:
        from PIL import Image, ImageDraw
    except ImportError as exc:
        raise SystemExit(
            "Pillow is required to generate the Windows icon. "
            "Install the project requirements first."
        ) from exc

    image = Image.new("RGBA", (256, 256), (49, 112, 220, 255))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((24, 24, 232, 232), radius=52, fill=(49, 112, 220, 255))
    draw.rounded_rectangle((104, 55, 152, 151), radius=24, fill="white")
    draw.arc((76, 96, 180, 193), start=0, end=180, fill="white", width=13)
    draw.line((128, 191, 128, 211), fill="white", width=13)
    draw.line((100, 211, 156, 211), fill="white", width=13)
    image.save(ICON_PATH, format="ICO", sizes=[(256, 256), (64, 64), (32, 32), (16, 16)])


def copy_offline_backups() -> None:
    model_source = SOURCE_LIB_DIRECTORY / MODEL_BACKUP_NAME
    engine_source = SOURCE_LIB_DIRECTORY / ENGINE_BACKUP_NAME
    missing = [path for path in (model_source, engine_source) if not path.is_file()]
    if missing:
        paths = "\n".join(f"  {path}" for path in missing)
        raise SystemExit(
            "The offline runtime assets are missing from the source assets\\lib folder:\n"
            f"{paths}"
        )

    LIB_DIRECTORY.mkdir(parents=True, exist_ok=True)
    copy2(model_source, LIB_DIRECTORY / MODEL_BACKUP_NAME)
    copy2(engine_source, LIB_DIRECTORY / ENGINE_BACKUP_NAME)

    config = {
        "model_path": f"lib/{MODEL_BACKUP_NAME}",
        "runtime_path": f"lib/{ENGINE_BACKUP_NAME}",
    }
    (DIST_DIRECTORY / CONFIG_NAME).write_text(
        json.dumps(config, indent=2) + "\n",
        encoding="utf-8",
    )
    (DIST_DIRECTORY / MODEL_BACKUP_NAME).unlink(missing_ok=True)
    (DIST_DIRECTORY / ENGINE_BACKUP_NAME).unlink(missing_ok=True)
    print(f"Offline model backup: {LIB_DIRECTORY / MODEL_BACKUP_NAME}")
    print(f"Offline runtime backup: {LIB_DIRECTORY / ENGINE_BACKUP_NAME}")
    print(f"Runtime configuration: {DIST_DIRECTORY / CONFIG_NAME}")


def main() -> None:
    if sys.platform != "win32":
        raise SystemExit("Run this build script on Windows to create the Windows executable.")

    create_icon()
    command = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--onefile",
        "--windowed",
        "--name",
        "GhostDictate",
        "--icon",
        str(ICON_PATH),
        "--add-data",
        f"{SVG_PATH};assets",
        "--collect-all",
        "needle",
        "--hidden-import",
        "PySide6.QtSvg",
        str(ROOT / "main.py"),
    ]
    copy_offline_backups()
    subprocess.run(command, cwd=ROOT, check=True)

    previous_executable = DIST_DIRECTORY / "Needle Voice Notes.exe"
    previous_executable.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
