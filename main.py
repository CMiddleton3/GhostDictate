from __future__ import annotations

import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

from PySide6.QtWidgets import QApplication

from ui import MainWindow


APP_NAME = "GhostDictate"


def configure_logging() -> None:
    """Write diagnostics locally without sending application data anywhere."""
    app_data = Path(os.environ.get("LOCALAPPDATA", Path.home()))
    log_directory = app_data / APP_NAME / "logs"
    handlers: list[logging.Handler] = [logging.StreamHandler()]

    try:
        log_directory.mkdir(parents=True, exist_ok=True)
        handlers.append(
            RotatingFileHandler(
                log_directory / "app.log",
                maxBytes=1_000_000,
                backupCount=3,
                encoding="utf-8",
            )
        )
    except OSError as exc:
        print(f"Could not create the application log file: {exc}", file=sys.stderr)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=handlers,
    )


def main() -> int:
    configure_logging()
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setOrganizationName("Cactus Compute")

    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
