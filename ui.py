from __future__ import annotations

import logging
from dataclasses import replace
from pathlib import Path

from PySide6.QtCore import QObject, QThread, Qt, Signal, Slot
from PySide6.QtGui import QCloseEvent, QIcon, QTextCursor
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from recorder import AudioCaptureError, AudioRecorder
from settings import AppSettings, LANGUAGES
from transcriber import NeedleTranscriber, TranscriptionResult


LOGGER = logging.getLogger(__name__)
APP_TITLE = "GhostDictate"


class TranscriptionWorker(QObject):
    completed = Signal(object)
    failed = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self._transcriber = NeedleTranscriber()

    @Slot(str, object)
    def transcribe(self, audio_path: str, settings: AppSettings) -> None:
        path = Path(audio_path)
        try:
            result = self._transcriber.transcribe(path, settings)
        except Exception as exc:
            LOGGER.exception("Transcription task failed")
            self.failed.emit(str(exc))
        else:
            self.completed.emit(result)
        finally:
            try:
                path.unlink(missing_ok=True)
            except OSError:
                LOGGER.exception("Could not remove temporary recording %s", path)


class MainWindow(QMainWindow):
    request_transcription = Signal(str, object)

    def __init__(self) -> None:
        super().__init__()
        self.settings = AppSettings.load()
        self.recorder = AudioRecorder()
        self._busy = False
        self._worker_thread = QThread(self)
        self._worker = TranscriptionWorker()
        self._worker.moveToThread(self._worker_thread)
        self.request_transcription.connect(
            self._worker.transcribe,
            Qt.ConnectionType.QueuedConnection,
        )
        self._worker.completed.connect(self._on_transcription_complete)
        self._worker.failed.connect(self._on_transcription_failed)
        self._worker_thread.start()

        self.setWindowTitle(APP_TITLE)
        self.setMinimumSize(780, 600)
        self.resize(1050, 720)
        icon_path = Path(__file__).parent / "assets" / "app_icon.svg"
        if icon_path.is_file():
            self.setWindowIcon(QIcon(str(icon_path)))

        self._build_ui()
        self._apply_theme()
        self._set_status("Ready")

    def _build_ui(self) -> None:
        central = QWidget(self)
        root = QVBoxLayout(central)
        root.setContentsMargins(26, 22, 26, 22)
        root.setSpacing(18)

        header = QHBoxLayout()
        title_block = QVBoxLayout()
        title = QLabel(APP_TITLE)
        title.setObjectName("appTitle")
        subtitle = QLabel("Private, local speech-to-text")
        subtitle.setObjectName("subtitle")
        title_block.addWidget(title)
        title_block.addWidget(subtitle)
        header.addLayout(title_block)
        header.addStretch(1)
        self.status_label = QLabel("Ready")
        self.status_label.setObjectName("statusBadge")
        header.addWidget(self.status_label, 0, Qt.AlignmentFlag.AlignTop)
        root.addLayout(header)

        content = QHBoxLayout()
        content.setSpacing(18)

        left_column = QVBoxLayout()
        left_column.setSpacing(14)

        recording_card = QFrame()
        recording_card.setObjectName("recordingCard")
        recording_layout = QVBoxLayout(recording_card)
        recording_layout.setContentsMargins(18, 14, 18, 14)
        recording_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        recording_hint = QLabel("Click to start recording")
        recording_hint.setObjectName("recordingHint")
        recording_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.mic_button = QPushButton("🎙")
        self.mic_button.setObjectName("micButton")
        self.mic_button.setFixedSize(126, 126)
        self.mic_button.setAccessibleName("Start or stop microphone recording")
        self.mic_button.clicked.connect(self._toggle_recording)
        recording_layout.addWidget(self.mic_button, 0, Qt.AlignmentFlag.AlignCenter)
        recording_layout.addWidget(recording_hint)
        self.recording_hint = recording_hint
        left_column.addWidget(recording_card)

        transcript_group = QGroupBox("Transcription")
        transcript_layout = QVBoxLayout(transcript_group)
        self.transcript_edit = QTextEdit()
        self.transcript_edit.setPlaceholderText(
            "Your transcription will appear here. You can edit it at any time."
        )
        self.transcript_edit.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )
        transcript_layout.addWidget(self.transcript_edit)
        left_column.addWidget(transcript_group, 1)

        actions = QGridLayout()
        self.copy_button = QPushButton("Copy to Clipboard")
        self.clear_button = QPushButton("Clear Text")
        self.save_button = QPushButton("Save to TXT")
        self.new_recording_button = QPushButton("Start New Recording")
        self.copy_button.clicked.connect(self._copy_text)
        self.clear_button.clicked.connect(self.transcript_edit.clear)
        self.save_button.clicked.connect(self._save_text)
        self.new_recording_button.clicked.connect(self._start_recording)
        actions.addWidget(self.copy_button, 0, 0)
        actions.addWidget(self.clear_button, 0, 1)
        actions.addWidget(self.save_button, 1, 0)
        actions.addWidget(self.new_recording_button, 1, 1)
        left_column.addLayout(actions)
        content.addLayout(left_column, 1)

        settings_panel = self._build_settings_panel()
        content.addWidget(settings_panel)
        root.addLayout(content, 1)

        self.setCentralWidget(central)

    def _build_settings_panel(self) -> QWidget:
        panel = QWidget()
        panel.setFixedWidth(260)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        language_group = QGroupBox("Language")
        language_layout = QVBoxLayout(language_group)
        self.auto_detect_checkbox = QCheckBox("Detect automatically")
        self.auto_detect_checkbox.setChecked(self.settings.auto_detect_language)
        self.auto_detect_checkbox.toggled.connect(self._on_auto_detect_changed)
        self.language_combo = QComboBox()
        for name, code in LANGUAGES:
            self.language_combo.addItem(f"{name} ({code})", code)
        selected_index = self.language_combo.findData(self.settings.language)
        if selected_index >= 0:
            self.language_combo.setCurrentIndex(selected_index)
        self.language_combo.setEnabled(not self.settings.auto_detect_language)
        self.language_combo.currentIndexChanged.connect(self._on_language_changed)
        language_layout.addWidget(self.auto_detect_checkbox)
        language_layout.addWidget(self.language_combo)
        layout.addWidget(language_group)

        model_group = QGroupBox("Whistle Model")
        model_layout = QVBoxLayout(model_group)
        model_path_layout = QHBoxLayout()
        self.model_path_edit = QLineEdit(self.settings.model_path or "")
        self.model_path_edit.setPlaceholderText("Use the default Whistle model")
        self.model_path_edit.editingFinished.connect(self._on_model_path_changed)
        browse_button = QPushButton("Browse")
        browse_button.clicked.connect(self._browse_model)
        model_path_layout.addWidget(self.model_path_edit, 1)
        model_path_layout.addWidget(browse_button)
        model_layout.addLayout(model_path_layout)
        self.model_info_label = QLabel(
            self.settings.model_path
            or "The default Whistle model downloads on first use."
        )
        self.model_info_label.setObjectName("detailLabel")
        self.model_info_label.setWordWrap(True)
        self.model_info_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        model_layout.addWidget(self.model_info_label)
        layout.addWidget(model_group)

        info_group = QGroupBox("Session")
        info_layout = QVBoxLayout(info_group)
        self.time_label = QLabel("Transcription time: --")
        self.time_label.setObjectName("detailLabel")
        self.time_label.setWordWrap(True)
        info_layout.addWidget(self.time_label)
        layout.addWidget(info_group)

        appearance_group = QGroupBox("Appearance")
        appearance_layout = QVBoxLayout(appearance_group)
        self.dark_mode_checkbox = QCheckBox("Dark mode")
        self.dark_mode_checkbox.setChecked(self.settings.dark_mode)
        self.dark_mode_checkbox.toggled.connect(self._on_dark_mode_changed)
        appearance_layout.addWidget(self.dark_mode_checkbox)
        layout.addWidget(appearance_group)
        layout.addStretch(1)
        return panel

    def _apply_theme(self) -> None:
        if self.settings.dark_mode:
            self.setStyleSheet(
                """
                QWidget { background: #202124; color: #e8eaed; font-size: 13px; }
                QMainWindow { background: #202124; }
                QLabel#appTitle { font-size: 24px; font-weight: 650; }
                QLabel#subtitle, QLabel#detailLabel, QLabel#recordingHint { color: #aeb4bd; }
                QLabel#statusBadge { background: #30343b; border-radius: 12px; padding: 7px 12px; }
                QGroupBox { border: 1px solid #3c4048; border-radius: 10px; margin-top: 10px; padding: 12px; font-weight: 600; }
                QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 4px; }
                QFrame#recordingCard { background: #282b30; border: 1px solid #3c4048; border-radius: 14px; }
                QTextEdit, QLineEdit, QComboBox { background: #292c31; border: 1px solid #454a52; border-radius: 7px; padding: 8px; selection-background-color: #3b82f6; }
                QPushButton { background: #343840; border: 1px solid #454a52; border-radius: 8px; padding: 9px 12px; }
                QPushButton:hover { background: #424751; }
                QPushButton:disabled { color: #777d86; }
                QPushButton#micButton { background: #3b82f6; border: none; border-radius: 63px; font-size: 46px; }
                QPushButton#micButton:hover { background: #5593fa; }
                QPushButton#micButton[state="recording"] { background: #df5252; }
                QPushButton#micButton:disabled { background: #545b66; }
                QCheckBox { spacing: 8px; }
                """
            )
        else:
            self.setStyleSheet(
                """
                QWidget { background: #f5f6f8; color: #202124; font-size: 13px; }
                QMainWindow { background: #f5f6f8; }
                QLabel#appTitle { font-size: 24px; font-weight: 650; }
                QLabel#subtitle, QLabel#detailLabel, QLabel#recordingHint { color: #606872; }
                QLabel#statusBadge { background: #e7eaf0; border-radius: 12px; padding: 7px 12px; }
                QGroupBox { border: 1px solid #d6dae1; border-radius: 10px; margin-top: 10px; padding: 12px; font-weight: 600; }
                QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 4px; }
                QFrame#recordingCard { background: #ffffff; border: 1px solid #d6dae1; border-radius: 14px; }
                QTextEdit, QLineEdit, QComboBox { background: #ffffff; border: 1px solid #c7ccd4; border-radius: 7px; padding: 8px; selection-background-color: #3b82f6; }
                QPushButton { background: #ffffff; border: 1px solid #c7ccd4; border-radius: 8px; padding: 9px 12px; }
                QPushButton:hover { background: #e9edf4; }
                QPushButton:disabled { color: #9299a3; }
                QPushButton#micButton { background: #3b82f6; border: none; border-radius: 63px; font-size: 46px; color: white; }
                QPushButton#micButton:hover { background: #5593fa; }
                QPushButton#micButton[state="recording"] { background: #df5252; }
                QPushButton#micButton:disabled { background: #aeb6c2; }
                QCheckBox { spacing: 8px; }
                """
            )
        self._refresh_status_style()

    def _set_status(self, status: str) -> None:
        self.status_label.setText(status)
        self.status_label.setProperty("state", status)
        self._refresh_status_style()

    def _refresh_status_style(self) -> None:
        self.status_label.style().unpolish(self.status_label)
        self.status_label.style().polish(self.status_label)

    def _set_recording_state(self, recording: bool) -> None:
        self.mic_button.setText("■" if recording else "🎙")
        self.mic_button.setProperty("state", "recording" if recording else "idle")
        self.mic_button.style().unpolish(self.mic_button)
        self.mic_button.style().polish(self.mic_button)
        self.recording_hint.setText(
            "Click to stop recording" if recording else "Click to start recording"
        )
        self.new_recording_button.setEnabled(not recording and not self._busy)

    def _toggle_recording(self) -> None:
        if self.recorder.is_recording:
            self._stop_recording()
        elif not self._busy:
            self._start_recording()

    def _start_recording(self) -> None:
        if self._busy or self.recorder.is_recording:
            return
        try:
            self.recorder.start()
        except AudioCaptureError as exc:
            LOGGER.warning("Audio capture could not start: %s", exc)
            self._set_status("Error")
            QMessageBox.warning(self, "Microphone unavailable", str(exc))
            return

        self._set_recording_state(True)
        self._set_status("Listening...")

    def _stop_recording(self) -> None:
        try:
            audio_path = self.recorder.stop()
        except AudioCaptureError as exc:
            LOGGER.warning("Audio capture failed: %s", exc)
            self._set_recording_state(False)
            self._set_status("Error")
            QMessageBox.warning(self, "Recording error", str(exc))
            return

        self._set_recording_state(False)
        self._busy = True
        self.mic_button.setEnabled(False)
        self.new_recording_button.setEnabled(False)
        self._set_status("Processing...")
        self.recording_hint.setText("Transcribing locally with Whistle...")
        self.request_transcription.emit(
            str(audio_path),
            replace(self.settings),
        )

    @Slot(object)
    def _on_transcription_complete(self, result: TranscriptionResult) -> None:
        self._busy = False
        self.mic_button.setEnabled(True)
        self.new_recording_button.setEnabled(True)
        self.recording_hint.setText(
            f"Detected language: {result.language}"
            if self.settings.auto_detect_language
            else "Click to start recording"
        )
        if result.text:
            cursor = self.transcript_edit.textCursor()
            cursor.movePosition(QTextCursor.MoveOperation.End)
            existing_text = self.transcript_edit.toPlainText()
            if existing_text and not existing_text.endswith("\n"):
                cursor.insertText("\n")
            cursor.insertText(result.text)
            self.transcript_edit.setTextCursor(cursor)
            self.transcript_edit.ensureCursorVisible()
        self.model_info_label.setText(result.model_info)
        self.time_label.setText(
            f"Transcription time: {result.elapsed_seconds:.2f} seconds"
        )
        self._set_status("Complete")

    @Slot(str)
    def _on_transcription_failed(self, message: str) -> None:
        self._busy = False
        self.mic_button.setEnabled(True)
        self.new_recording_button.setEnabled(True)
        self.recording_hint.setText("Click to start recording")
        self._set_status("Error")
        QMessageBox.warning(self, "Transcription error", message)

    def _copy_text(self) -> None:
        QApplication.clipboard().setText(self.transcript_edit.toPlainText())

    def _save_text(self) -> None:
        text = self.transcript_edit.toPlainText()
        if not text:
            QMessageBox.information(self, "Nothing to save", "The transcription is empty.")
            return
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save transcription",
            "transcription.txt",
            "Text files (*.txt)",
        )
        if not file_path:
            return
        try:
            Path(file_path).write_text(text, encoding="utf-8")
        except OSError as exc:
            LOGGER.exception("Could not save transcription to %s", file_path)
            QMessageBox.critical(self, "Save failed", f"Could not save the file:\n{exc}")

    def _on_auto_detect_changed(self, enabled: bool) -> None:
        self.settings.auto_detect_language = enabled
        self.language_combo.setEnabled(not enabled)
        self._save_settings()

    def _on_language_changed(self, _index: int) -> None:
        language = self.language_combo.currentData()
        if language:
            self.settings.language = language
            self._save_settings()

    def _on_dark_mode_changed(self, enabled: bool) -> None:
        self.settings.dark_mode = enabled
        self._apply_theme()
        self._save_settings()

    def _on_model_path_changed(self) -> None:
        value = self.model_path_edit.text().strip()
        self.settings.model_path = (
            str(Path(value).expanduser().resolve()) if value else None
        )
        self.model_info_label.setText(
            self.settings.model_path
            or "The default Whistle model downloads on first use."
        )
        self._save_settings()

    def _browse_model(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Whistle model",
            "",
            "Cactus model files (*.cact);;All files (*)",
        )
        if file_path:
            self.model_path_edit.setText(file_path)
            self._on_model_path_changed()

    def _save_settings(self) -> None:
        try:
            self.settings.save()
        except OSError as exc:
            LOGGER.exception("Could not save application settings")
            QMessageBox.warning(
                self,
                "Settings could not be saved",
                f"Your change is active for this session, but could not be saved:\n{exc}",
            )

    def closeEvent(self, event: QCloseEvent) -> None:
        if self.recorder.is_recording:
            try:
                temporary_audio = self.recorder.stop()
                temporary_audio.unlink(missing_ok=True)
            except (AudioCaptureError, OSError):
                LOGGER.exception("Could not clean up the microphone while closing")
        self._worker_thread.quit()
        self._worker_thread.wait()
        super().closeEvent(event)
