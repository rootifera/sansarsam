from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re

from PySide6.QtCore import Qt, QFileSystemWatcher, QTimer, QSettings
from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QProgressDialog,
    QPlainTextEdit,
    QSpinBox,
    QVBoxLayout,
    QWidget,
    QFileDialog,
)
from PySide6.QtCore import QObject, QEventLoop, QThread, Signal
import subprocess

from services.greaseweazle import (
    build_read_command,
    build_write_command,
    run_command,
    detect_gw_executable,
)

SUPPORTED_IMAGE_SUFFIXES = {
    ".a2r", ".adf", ".ads", ".adm", ".adl", ".ctr", ".d1m", ".d2m", ".d4m",
    ".d64", ".d71", ".d81", ".d88", ".dcp", ".dim", ".dmk", ".do", ".dsd",
    ".dsk", ".edsk", ".fd", ".fdi", ".hdm", ".hfe", ".ima", ".img", ".imd",
    ".ipf", ".mgt", ".msa", ".nfd", ".nsi", ".po", ".raw", ".sf7", ".scp",
    ".ssd", ".st", ".td0", ".xdf"
}

COMMON_GW_FORMATS = [
    "ibm.1440",
    "ibm.720",
    "ibm.1200",
    "ibm.360",
    "amiga.amigados",
    "amiga.amigados_hd",
    "atarist.720",
    "commodore.1541",
    "apple2.prodos.140",
    "pc98.2hd",
]

ALL_GW_FORMATS = [
    "acorn.adfs.160",
    "acorn.adfs.1600",
    "acorn.adfs.320",
    "acorn.adfs.640",
    "acorn.adfs.800",
    "acorn.dfs.ds",
    "acorn.dfs.ds80",
    "acorn.dfs.ss",
    "acorn.dfs.ss80",
    "akai.1600",
    "akai.800",
    "amiga.amigados",
    "amiga.amigados_hd",
    "apple2.appledos.140",
    "apple2.nofs.140",
    "apple2.prodos.140",
    "atari.90",
    "atarist.360",
    "atarist.400",
    "atarist.440",
    "atarist.720",
    "atarist.800",
    "atarist.880",
    "coco.decb",
    "coco.decb.40t",
    "coco.os9.40ds",
    "coco.os9.40ss",
    "coco.os9.80ds",
    "coco.os9.80ss",
    "commodore.1541",
    "commodore.1571",
    "commodore.1581",
    "commodore.cmd.fd2000.dd",
    "commodore.cmd.fd2000.hd",
    "commodore.cmd.fd4000.ed",
    "dec.rx01",
    "dec.rx02",
    "dragon.40ds",
    "dragon.40ss",
    "dragon.80ds",
    "dragon.80ss",
    "ensoniq.1600",
    "ensoniq.800",
    "ensoniq.mirage",
    "epson.qx10.320",
    "epson.qx10.396",
    "epson.qx10.399",
    "epson.qx10.400",
    "epson.qx10.booter",
    "epson.qx10.logo",
    "gem.1600",
    "hp.mmfm.9885",
    "hp.mmfm.9895",
    "ibm.1200",
    "ibm.1440",
    "ibm.160",
    "ibm.1680",
    "ibm.180",
    "ibm.2880",
    "ibm.320",
    "ibm.360",
    "ibm.720",
    "ibm.800",
    "ibm.dmf",
    "ibm.scan",
    "mac.400",
    "mac.800",
    "micropolis.100tpi.ds",
    "micropolis.100tpi.ds.275",
    "micropolis.100tpi.ss",
    "micropolis.100tpi.ss.275",
    "micropolis.48tpi.ds",
    "micropolis.48tpi.ds.275",
    "micropolis.48tpi.ss",
    "micropolis.48tpi.ss.275",
    "mm1.os9.80dshd_32",
    "mm1.os9.80dshd_33",
    "mm1.os9.80dshd_36",
    "mm1.os9.80dshd_37",
    "msx.1d",
    "msx.1dd",
    "msx.2d",
    "msx.2dd",
    "northstar.fm.ds",
    "northstar.fm.ss",
    "northstar.mfm.ds",
    "northstar.mfm.ss",
    "occ1.dd",
    "occ1.sd",
    "olivetti.m20",
    "pc98.2d",
    "pc98.2dd",
    "pc98.2hd",
    "pc98.2hs",
    "pc98.n88basic.hd",
    "raw.125",
    "raw.250",
    "raw.500",
    "sci.prophet",
    "sega.sf7000",
    "thomson.1s160",
    "thomson.1s320",
    "thomson.1s80",
    "thomson.2s160",
    "thomson.2s320",
    "tsc.flex.dsdd",
    "tsc.flex.ssdd",
    "zx.3dos.ds80",
    "zx.3dos.ss40",
    "zx.d80.ds80",
    "zx.fdd3000.ds80",
    "zx.fdd3000.ss40",
    "zx.kempston.ds80",
    "zx.kempston.ss40",
    "zx.opus.ds80",
    "zx.opus.ss40",
    "zx.plusd.ds80",
    "zx.quorum.ds80",
    "zx.rocky.ds80",
    "zx.rocky.ss40",
    "zx.trdos.ds80",
    "zx.turbodrive.ds40",
    "zx.turbodrive.ds80",
    "zx.watford.ds80",
    "zx.watford.ss40",
]

COMMON_OUTPUT_TYPES = [
    "IMG",
    "SCP",
    "DSK",
    "ADF",
    "IPF",
    "HFE",
]

ALL_OUTPUT_TYPES = sorted(suffix[1:].upper() for suffix in SUPPORTED_IMAGE_SUFFIXES)

LOAD_MORE_FORMATS_TEXT = "Load more..."


@dataclass
class DiskAction:
    retry: bool = False
    skip: bool = False
    abort: bool = False


class CommandWorker(QObject):
    output = Signal(str)
    finished = Signal(object)

    def __init__(self, command: list[str]) -> None:
        super().__init__()
        self._command = command
        self._process: subprocess.Popen[str] | None = None
        self._cancelled = False

    def run(self) -> None:
        result = run_command(
            self._command,
            self.output.emit,
            on_process_started=self._set_process,
        )
        if self._cancelled:
            result.cancelled = True
            if result.return_code == 0:
                result.return_code = -1
        self.finished.emit(result)

    def cancel(self) -> None:
        self._cancelled = True
        if self._process is None:
            return
        if self._process.poll() is not None:
            return
        self._process.terminate()
        try:
            self._process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            self._process.kill()

    def _set_process(self, process: subprocess.Popen[str]) -> None:
        self._process = process


class WriteImagesTab(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self._settings = QSettings()
        self._loading_settings = False
        self._group_index = -1
        self.setAcceptDrops(True)
        self._folder_watcher = QFileSystemWatcher(self)
        self._folder_watcher.directoryChanged.connect(self._on_watched_folder_changed)
        self._build_ui()
        self._load_settings()

    def _select_all_files(self) -> None:
        for index in range(self.file_list.count()):
            item = self.file_list.item(index)
            item.setCheckState(Qt.Checked)

    def _select_no_files(self) -> None:
        for index in range(self.file_list.count()):
            item = self.file_list.item(index)
            item.setCheckState(Qt.Unchecked)

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        folder_row = QHBoxLayout()
        self.folder_input = QLineEdit()
        self.folder_input.setReadOnly(True)
        browse_btn = QPushButton("Select Folder")
        browse_btn.clicked.connect(self._select_folder)
        scan_btn = QPushButton("Scan")
        scan_btn.clicked.connect(self._scan_folder)
        folder_row.addWidget(QLabel("Image Folder:"))
        folder_row.addWidget(self.folder_input, 1)
        folder_row.addWidget(browse_btn)
        folder_row.addWidget(scan_btn)

        layout.addLayout(folder_row)

        self.file_list = QListWidget()
        self.file_list.setDragDropMode(QListWidget.InternalMove)
        layout.addWidget(QLabel("Detected Images (drag to reorder):"))
        layout.addWidget(self.file_list, 1)

        reorder_buttons = QHBoxLayout()
        move_up_btn = QPushButton("Move Up")
        move_down_btn = QPushButton("Move Down")
        select_all_btn = QPushButton("Select All")
        select_none_btn = QPushButton("Select None")
        select_group_btn = QPushButton("Select Group")

        move_up_btn.clicked.connect(self._move_selected_up)
        move_down_btn.clicked.connect(self._move_selected_down)
        select_all_btn.clicked.connect(self._select_all_files)
        select_none_btn.clicked.connect(self._select_no_files)
        select_group_btn.clicked.connect(self._select_next_group)

        reorder_buttons.addWidget(move_up_btn)
        reorder_buttons.addWidget(move_down_btn)
        reorder_buttons.addWidget(select_all_btn)
        reorder_buttons.addWidget(select_none_btn)
        reorder_buttons.addWidget(select_group_btn)
        reorder_buttons.addStretch(1)
        layout.addLayout(reorder_buttons)

        options_group = QGroupBox("Options")
        options_layout = QFormLayout(options_group)

        self._all_formats_loaded = False
        self.format_combo = QComboBox()
        self.custom_format_checkbox = QCheckBox("Use custom format")
        self.custom_format_input = QLineEdit()
        self.custom_format_input.setPlaceholderText("e.g. ibm.1440")
        self.custom_format_input.setEnabled(False)

        self._populate_format_combo()

        self.format_combo.currentIndexChanged.connect(self._on_format_changed)
        self.format_combo.currentIndexChanged.connect(self._save_settings)

        self.custom_format_checkbox.toggled.connect(self._on_custom_format_toggled)
        self.custom_format_checkbox.toggled.connect(self._save_settings)

        self.custom_format_input.textChanged.connect(self._save_settings)

        self.verify_checkbox = QCheckBox("Verify")
        self.verify_checkbox.setChecked(True)
        self.verify_checkbox.toggled.connect(self._save_settings)

        self.extra_flags_input = QLineEdit()
        self.extra_flags_input.textChanged.connect(self._save_settings)

        options_layout.addRow("Disk format:", self.format_combo)
        options_layout.addRow("Custom:", self.custom_format_checkbox)
        options_layout.addRow("Custom format string:", self.custom_format_input)
        options_layout.addRow("Verify:", self.verify_checkbox)
        options_layout.addRow("Extra flags:", self.extra_flags_input)
        layout.addWidget(options_group)

        self.start_btn = QPushButton("Start Writing")
        self.start_btn.setMinimumHeight(40)
        self.start_btn.setStyleSheet("""
        QPushButton {
            background-color: rgb(58, 110, 165);
            color: white;
            font-weight: bold;
            padding: 8px;
            border-radius: 4px;
            border: 1px solid rgb(40, 80, 120);
        }
        QPushButton:hover {
            background-color: rgb(70, 125, 185);
        }
        QPushButton:pressed {
            background-color: rgb(40, 90, 140);
        }
        QPushButton:disabled {
            background-color: rgb(140, 140, 140);
            color: rgb(220, 220, 220);
        }
        """)
        self.start_btn.clicked.connect(self._start_write)
        layout.addWidget(self.start_btn)

        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        layout.addWidget(QLabel("Log:"))
        layout.addWidget(self.log, 1)

    def _save_settings(self) -> None:
        if self._loading_settings:
            return

        self._settings.setValue("write/folder", self.folder_input.text().strip())
        self._settings.setValue("write/verify", self.verify_checkbox.isChecked())
        self._settings.setValue("write/extra_flags", self.extra_flags_input.text())

        self._settings.setValue(
            "write/custom_format_enabled",
            self.custom_format_checkbox.isChecked(),
        )
        self._settings.setValue(
            "write/custom_format_text",
            self.custom_format_input.text(),
        )

        current_text = self.format_combo.currentText().strip()
        if current_text and current_text != LOAD_MORE_FORMATS_TEXT:
            self._settings.setValue("write/selected_format", current_text)

    def _load_settings(self) -> None:
        self._loading_settings = True
        folder = self._settings.value("write/folder", "", type=str)
        verify = self._settings.value("write/verify", True, type=bool)
        extra_flags = self._settings.value("write/extra_flags", "", type=str)

        custom_enabled = self._settings.value("write/custom_format_enabled", False, type=bool)
        custom_text = self._settings.value("write/custom_format_text", "", type=str)
        selected_format = self._settings.value("write/selected_format", "ibm.1440", type=str)


        self.verify_checkbox.setChecked(verify)
        self.extra_flags_input.setText(extra_flags)

        combo_index = self.format_combo.findText(selected_format)
        if combo_index >= 0:
            self.format_combo.setCurrentIndex(combo_index)

        self.custom_format_checkbox.setChecked(custom_enabled)
        self.custom_format_input.setText(custom_text)
        self._on_custom_format_toggled(custom_enabled)

        if folder:
            folder_path = Path(folder)
            self.folder_input.setText(folder)
            if folder_path.exists() and folder_path.is_dir():
                self._set_watched_folder(folder)
                self._scan_folder()

        self._loading_settings = False

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event):
        urls = event.mimeData().urls()
        if not urls:
            return

        paths = [Path(url.toLocalFile()) for url in urls if url.isLocalFile()]
        if not paths:
            return

        # Folder dropped
        for path in paths:
            if path.is_dir():
                self._set_folder_from_drop(path)
                return

        # File dropped → use parent folder
        first_file = paths[0]
        if first_file.is_file():
            self._set_folder_from_drop(first_file.parent)

    def _set_folder_from_drop(self, folder: Path):
        folder_str = str(folder)

        if not folder.exists() or not folder.is_dir():
            return

        self.folder_input.setText(folder_str)
        self._set_watched_folder(folder_str)
        self._scan_folder()
        self._save_settings()

    def _select_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Select image folder")
        if folder:
            self.folder_input.setText(folder)
            self._set_watched_folder(folder)
            self._scan_folder()
            self._save_settings()

    def _scan_folder(self) -> None:
        folder_text = self.folder_input.text().strip()
        if not folder_text:
            QMessageBox.warning(self, "Missing Folder", "Please select a folder first.")
            return

        folder = Path(folder_text)
        if not folder.exists() or not folder.is_dir():
            QMessageBox.warning(self, "Invalid Folder", "Selected folder is not valid.")
            return

        found = [
            path
            for path in folder.iterdir()
            if path.is_file() and path.suffix.lower() in SUPPORTED_IMAGE_SUFFIXES
        ]
        current_items: dict[str, Qt.CheckState] = {}
        current_order: list[str] = []
        for index in range(self.file_list.count()):
            item = self.file_list.item(index)
            path_value = item.data(Qt.UserRole)
            if path_value:
                path_str = str(path_value)
                current_items[path_str] = item.checkState()
                current_order.append(path_str)

        found_by_path = {str(path): path for path in found}
        merged_paths: list[str] = [path for path in current_order if path in found_by_path]
        for new_path in sorted(found_by_path.values(), key=_disk_sort_key):
            new_path_str = str(new_path)
            if new_path_str not in current_items:
                merged_paths.append(new_path_str)

        self.file_list.clear()
        for path_str in merged_paths:
            file_path = Path(path_str)
            item = QListWidgetItem(file_path.name)
            item.setData(Qt.UserRole, path_str)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(current_items.get(path_str, Qt.Checked))
            self.file_list.addItem(item)

        self._append_log(f"Found {len(found_by_path)} supported image file(s).")

    def _start_write(self) -> None:
        disk_files = self._collect_disk_files()
        if not disk_files:
            QMessageBox.warning(self, "No Files", "No images loaded to write.")
            return

        self._set_busy(True)
        try:
            for disk_index, image_path in enumerate(disk_files, start=1):
                if not self._prompt_continue(
                        title="Insert Disk",
                        message=f"Insert floppy for Disk {disk_index} and click Continue.",
                ):
                    self._append_log("Write workflow stopped by user.")
                    return

                while True:
                    command = build_write_command(
                        image_path=image_path,
                        fmt=self._selected_format(),
                        verify=self.verify_checkbox.isChecked(),
                        extra_flags=self.extra_flags_input.text(),
                        gw_executable=self._settings.value("app/gw_path", detect_gw_executable(), type=str).strip() or "gw",
                    )
                    result = self._run_command_with_progress(command)
                    if result.cancelled:
                        self._append_log("Write workflow aborted by user during command execution.")
                        return
                    if result.return_code == 0:
                        if self._looks_like_cli_failure(result.output_lines):
                            self._append_log(
                                f"Disk {disk_index}: command output indicates a failure."
                            )
                            action = self._failure_action(disk_index)
                            if action.retry:
                                continue
                            if action.skip:
                                self._append_log(f"Disk {disk_index}: skipped after error.")
                                break
                            if action.abort:
                                self._append_log("Write workflow aborted.")
                                return
                        self._append_log(f"Disk {disk_index}: completed.")
                        break

                    action = self._failure_action(disk_index)
                    if action.retry:
                        continue
                    if action.skip:
                        self._append_log(f"Disk {disk_index}: skipped after error.")
                        break
                    if action.abort:
                        self._append_log("Write workflow aborted.")
                        return
        finally:
            self._set_busy(False)

    def _populate_format_combo(self) -> None:
        current_value = self.format_combo.currentText().strip()
        self.format_combo.blockSignals(True)
        self.format_combo.clear()
        self.format_combo.addItems(COMMON_GW_FORMATS)
        if self._all_formats_loaded:
            self.format_combo.insertSeparator(self.format_combo.count())
            for fmt in ALL_GW_FORMATS:
                if fmt not in COMMON_GW_FORMATS:
                    self.format_combo.addItem(fmt)
        else:
            self.format_combo.insertSeparator(self.format_combo.count())
            self.format_combo.addItem(LOAD_MORE_FORMATS_TEXT)

        if current_value and current_value != LOAD_MORE_FORMATS_TEXT:
            index = self.format_combo.findText(current_value)
            if index >= 0:
                self.format_combo.setCurrentIndex(index)
            else:
                default_index = self.format_combo.findText("ibm.1440")
                self.format_combo.setCurrentIndex(default_index if default_index >= 0 else 0)
        else:
            default_index = self.format_combo.findText("ibm.1440")
            self.format_combo.setCurrentIndex(default_index if default_index >= 0 else 0)
        self.format_combo.blockSignals(False)

    def _on_format_changed(self, index: int) -> None:
        if index < 0:
            return
        if self.format_combo.itemText(index) != LOAD_MORE_FORMATS_TEXT:
            return

        previous_format = "ibm.1440"
        current_text = self.format_combo.currentText().strip()
        if current_text and current_text != LOAD_MORE_FORMATS_TEXT:
            previous_format = current_text
        elif index > 0:
            previous_format = self.format_combo.itemText(index - 1)

        self._all_formats_loaded = True
        self._populate_format_combo()
        restored_index = self.format_combo.findText(previous_format)
        if restored_index >= 0:
            self.format_combo.setCurrentIndex(restored_index)

        self._save_settings()
        QTimer.singleShot(0, self.format_combo.showPopup)

    def _on_custom_format_toggled(self, checked: bool) -> None:
        self.format_combo.setEnabled(not checked)
        self.custom_format_input.setEnabled(checked)
        if checked and not self.custom_format_input.text().strip():
            self.custom_format_input.setText(self._selected_dropdown_format())
        self._save_settings()

    def _selected_dropdown_format(self) -> str:
        current_text = self.format_combo.currentText().strip()
        if current_text == LOAD_MORE_FORMATS_TEXT:
            return "ibm.1440"
        return current_text

    def _selected_format(self) -> str:
        if self.custom_format_checkbox.isChecked():
            return self.custom_format_input.text().strip()
        return self._selected_dropdown_format()

    def _collect_disk_files(self) -> list[Path]:
        files: list[Path] = []
        for index in range(self.file_list.count()):
            item = self.file_list.item(index)
            path_value = item.data(Qt.UserRole)
            if path_value and item.checkState() == Qt.Checked:
                files.append(Path(path_value))
        return files

    def _set_watched_folder(self, folder_path: str) -> None:
        existing_dirs = self._folder_watcher.directories()
        if existing_dirs:
            self._folder_watcher.removePaths(existing_dirs)
        self._folder_watcher.addPath(folder_path)

    def _on_watched_folder_changed(self, folder_path: str) -> None:
        if folder_path == self.folder_input.text().strip():
            self._scan_folder()

    def _failure_action(self, disk_index: int) -> DiskAction:
        msg = QMessageBox(self)
        msg.setIcon(QMessageBox.Warning)
        msg.setWindowTitle("Command Failed")
        msg.setText(f"Disk {disk_index} failed.")
        retry_btn = msg.addButton("Retry", QMessageBox.AcceptRole)
        skip_btn = msg.addButton("Skip", QMessageBox.DestructiveRole)
        abort_btn = msg.addButton("Abort", QMessageBox.RejectRole)
        msg.exec()

        clicked = msg.clickedButton()
        return DiskAction(
            retry=clicked is retry_btn,
            skip=clicked is skip_btn,
            abort=clicked is abort_btn,
        )

    def _prompt_continue(self, title: str, message: str) -> bool:
        box = QMessageBox(self)
        box.setWindowTitle(title)
        box.setText(message)
        continue_btn = box.addButton("Continue", QMessageBox.AcceptRole)
        cancel_btn = box.addButton("Cancel", QMessageBox.RejectRole)
        box.exec()
        return box.clickedButton() is continue_btn and box.clickedButton() is not cancel_btn

    def _append_log(self, text: str) -> None:
        self.log.appendPlainText(text)
        self.log.moveCursor(QTextCursor.End)

    def _set_busy(self, busy: bool) -> None:
        self.start_btn.setEnabled(not busy)

    def _run_command_with_progress(self, command: list[str]):
        progress = QProgressDialog("Running gw command...", "Abort", 0, 0, self)
        progress.setWindowTitle("Greaseweazle Running")
        progress.setWindowModality(Qt.ApplicationModal)
        progress.setMinimumDuration(0)

        thread = QThread(self)
        worker = CommandWorker(command)
        worker.moveToThread(thread)

        result_holder: dict[str, object] = {}
        loop = QEventLoop(self)

        worker.output.connect(self._append_log)
        worker.finished.connect(lambda result: result_holder.setdefault("result", result))
        worker.finished.connect(loop.quit)
        thread.started.connect(worker.run)
        progress.canceled.connect(
            lambda: (self._append_log("[abort requested]"), worker.cancel())
        )

        thread.start()
        progress.show()
        loop.exec()

        progress.hide()
        thread.quit()
        thread.wait()

        return result_holder["result"]

    def _looks_like_cli_failure(self, output_lines: list[str] | None) -> bool:
        if not output_lines:
            return False
        error_markers = ("error", "failed", "no flux", "no index", "no disk")
        lowered = " ".join(output_lines).lower()
        return any(marker in lowered for marker in error_markers)

    def _move_selected_up(self) -> None:
        current = self.file_list.currentRow()
        if current <= 0:
            return
        item = self.file_list.takeItem(current)
        self.file_list.insertItem(current - 1, item)
        self.file_list.setCurrentRow(current - 1)

    def _move_selected_down(self) -> None:
        current = self.file_list.currentRow()
        if current < 0 or current >= self.file_list.count() - 1:
            return
        item = self.file_list.takeItem(current)
        self.file_list.insertItem(current + 1, item)
        self.file_list.setCurrentRow(current + 1)

    def _get_groups(self) -> list[str]:
        groups = []
        seen = set()

        for index in range(self.file_list.count()):
            item = self.file_list.item(index)
            path_value = item.data(Qt.UserRole)
            if not path_value:
                continue

            group = self._group_name_from_path(path_value)

            if group not in seen:
                seen.add(group)
                groups.append(group)

        return groups

    def _select_next_group(self) -> None:
        groups = self._get_groups()
        if not groups:
            return

        self._group_index = (self._group_index + 1) % len(groups)
        target_group = groups[self._group_index]

        for index in range(self.file_list.count()):
            item = self.file_list.item(index)
            path_value = item.data(Qt.UserRole)
            if not path_value:
                continue

            group = self._group_name_from_path(path_value)

            if group == target_group:
                item.setCheckState(Qt.Checked)
            else:
                item.setCheckState(Qt.Unchecked)

    def _group_name_from_path(self, path_value) -> str:
        name = Path(path_value).stem.lower()

        name = re.sub(r"\s*\[[^\]]+\]", "", name)
        name = re.sub(r"\s*\((?:disk|disc)\s*\d+\)", "", name, flags=re.IGNORECASE)
        name = re.sub(r"\s*(?:disk|disc)\s*\d+", "", name, flags=re.IGNORECASE)
        name = re.sub(r"\s+", " ", name).strip()

        return name


class CreateImagesTab(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self._settings = QSettings()
        self._loading_settings = False
        self.setAcceptDrops(True)
        self._build_ui()
        self._load_settings()

        self._settings.setValue("create/label", self.label_input.text())
        self._settings.setValue("create/disk_count", self.disk_count_input.value())
        self._settings.setValue("create/output_type", self.output_type_combo.currentText())
        self._settings.setValue("create/output_folder", self.output_folder_input.text().strip())
        self._settings.setValue("create/extra_flags", self.extra_flags_input.text())

        self._settings.setValue(
            "create/custom_format_enabled",
            self.custom_format_checkbox.isChecked(),
        )
        self._settings.setValue(
            "create/custom_format_text",
            self.custom_format_input.text(),
        )

        current_text = self.format_combo.currentText().strip()
        if current_text and current_text != LOAD_MORE_FORMATS_TEXT:
            self._settings.setValue("create/selected_format", current_text)

    def _populate_output_type_combo(self) -> None:
        current_value = self.output_type_combo.currentText().strip()

        self.output_type_combo.blockSignals(True)
        self.output_type_combo.clear()

        self.output_type_combo.addItems(COMMON_OUTPUT_TYPES)

        if self._all_output_types_loaded:
            self.output_type_combo.insertSeparator(self.output_type_combo.count())
            for ext in ALL_OUTPUT_TYPES:
                if ext not in COMMON_OUTPUT_TYPES:
                    self.output_type_combo.addItem(ext)
        else:
            self.output_type_combo.insertSeparator(self.output_type_combo.count())
            self.output_type_combo.addItem(LOAD_MORE_FORMATS_TEXT)

        if current_value and current_value != LOAD_MORE_FORMATS_TEXT:
            index = self.output_type_combo.findText(current_value)
            if index >= 0:
                self.output_type_combo.setCurrentIndex(index)
            else:
                self.output_type_combo.setCurrentIndex(0)
        else:
            self.output_type_combo.setCurrentIndex(0)

        self.output_type_combo.blockSignals(False)

    def _on_output_type_changed(self, index: int) -> None:
        if index < 0:
            return

        if self.output_type_combo.itemText(index) != LOAD_MORE_FORMATS_TEXT:
            return

        previous_value = self.output_type_combo.currentText().strip()
        if previous_value == LOAD_MORE_FORMATS_TEXT and index > 0:
            previous_value = self.output_type_combo.itemText(index - 1)

        self._all_output_types_loaded = True
        self._populate_output_type_combo()

        restored_index = self.output_type_combo.findText(previous_value)
        if restored_index >= 0:
            self.output_type_combo.setCurrentIndex(restored_index)

        QTimer.singleShot(0, self.output_type_combo.showPopup)

    def _save_settings(self) -> None:
        if self._loading_settings:
            return

        self._settings.setValue("create/label", self.label_input.text())
        self._settings.setValue("create/disk_count", self.disk_count_input.value())
        self._settings.setValue("create/output_type", self.output_type_combo.currentText())
        self._settings.setValue("create/output_folder", self.output_folder_input.text().strip())
        self._settings.setValue("create/extra_flags", self.extra_flags_input.text())

        self._settings.setValue(
            "create/custom_format_enabled",
            self.custom_format_checkbox.isChecked(),
        )
        self._settings.setValue(
            "create/custom_format_text",
            self.custom_format_input.text(),
        )

        current_text = self.format_combo.currentText().strip()
        if current_text and current_text != LOAD_MORE_FORMATS_TEXT:
            self._settings.setValue("create/selected_format", current_text)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event):
        urls = event.mimeData().urls()
        if not urls:
            return

        paths = [Path(url.toLocalFile()) for url in urls if url.isLocalFile()]
        if not paths:
            return

        for path in paths:
            if path.is_dir():
                self._set_output_folder_from_drop(path)
                return

        first_file = paths[0]
        if first_file.is_file():
            self._set_output_folder_from_drop(first_file.parent)

    def _set_output_folder_from_drop(self, folder: Path) -> None:
        folder_str = str(folder)

        if not folder.exists() or not folder.is_dir():
            return

        self.output_folder_input.setText(folder_str)
        self._save_settings()

    def _load_settings(self) -> None:
        self._loading_settings = True

        label = self._settings.value("create/label", "", type=str)
        disk_count = self._settings.value("create/disk_count", 1, type=int)
        output_type = self._settings.value("create/output_type", "IMG", type=str)
        output_folder = self._settings.value("create/output_folder", "", type=str)
        extra_flags = self._settings.value("create/extra_flags", "", type=str)
        custom_enabled = self._settings.value("create/custom_format_enabled", False, type=bool)
        custom_text = self._settings.value("create/custom_format_text", "", type=str)
        selected_format = self._settings.value("create/selected_format", "ibm.1440", type=str)

        self.label_input.setText(label)
        self.disk_count_input.setValue(disk_count)
        self.output_folder_input.setText(output_folder)
        self.extra_flags_input.setText(extra_flags)

        if output_type not in COMMON_OUTPUT_TYPES and output_type in ALL_OUTPUT_TYPES:
            self._all_output_types_loaded = True
            self._populate_output_type_combo()

        output_type_index = self.output_type_combo.findText(output_type)
        if output_type_index >= 0:
            self.output_type_combo.setCurrentIndex(output_type_index)

        format_index = self.format_combo.findText(selected_format)
        if format_index >= 0:
            self.format_combo.setCurrentIndex(format_index)

        self.custom_format_checkbox.setChecked(custom_enabled)
        self.custom_format_input.setText(custom_text)
        self._on_custom_format_toggled(custom_enabled)

        self._loading_settings = False

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)

        destination_row = QHBoxLayout()
        self.output_folder_input = QLineEdit()
        self.output_folder_input.textChanged.connect(self._save_settings)
        self.output_folder_input.setReadOnly(True)
        select_output_btn = QPushButton("Select Output Folder")
        select_output_btn.clicked.connect(self._select_output_folder)
        destination_row.addWidget(QLabel("Output Folder:"))
        destination_row.addWidget(self.output_folder_input, 1)
        destination_row.addWidget(select_output_btn)
        root.addLayout(destination_row)

        details_group = QGroupBox("Image Details")
        details_layout = QGridLayout(details_group)

        self.label_input = QLineEdit()
        self.label_input.textChanged.connect(self._save_settings)
        self.disk_count_input = QSpinBox()
        self.disk_count_input.setMinimum(1)
        self.disk_count_input.setValue(1)
        self.disk_count_input.valueChanged.connect(self._save_settings)

        self.output_type_combo = QComboBox()
        self._all_output_types_loaded = False
        self._populate_output_type_combo()
        self.output_type_combo.currentIndexChanged.connect(self._on_output_type_changed)
        self.output_type_combo.currentIndexChanged.connect(self._save_settings)

        self._all_formats_loaded = False
        self.format_combo = QComboBox()
        self.custom_format_checkbox = QCheckBox("Use custom format")
        self.custom_format_input = QLineEdit()
        self.custom_format_input.setPlaceholderText("e.g. ibm.1440")
        self.custom_format_input.setEnabled(False)
        self.custom_format_input.textChanged.connect(self._save_settings)

        self._populate_format_combo()
        self.format_combo.currentIndexChanged.connect(self._on_format_changed)
        self.format_combo.currentIndexChanged.connect(self._save_settings)
        self.custom_format_checkbox.toggled.connect(self._on_custom_format_toggled)
        self.custom_format_checkbox.toggled.connect(self._save_settings)

        self.extra_flags_input = QLineEdit()
        self.extra_flags_input.textChanged.connect(self._save_settings)

        details_layout.addWidget(QLabel("Label:"), 0, 0)
        details_layout.addWidget(self.label_input, 0, 1)
        details_layout.addWidget(QLabel("Total disks:"), 1, 0)
        details_layout.addWidget(self.disk_count_input, 1, 1)
        details_layout.addWidget(QLabel("Output type:"), 2, 0)
        details_layout.addWidget(self.output_type_combo, 2, 1)
        details_layout.addWidget(QLabel("Disk format:"), 3, 0)
        details_layout.addWidget(self.format_combo, 3, 1)
        details_layout.addWidget(self.custom_format_checkbox, 4, 1)
        details_layout.addWidget(QLabel("Custom format string:"), 5, 0)
        details_layout.addWidget(self.custom_format_input, 5, 1)
        details_layout.addWidget(QLabel("Extra flags:"), 6, 0)
        details_layout.addWidget(self.extra_flags_input, 6, 1)

        root.addWidget(details_group)

        self.start_btn = QPushButton("Start Reading")
        self.start_btn.setMinimumHeight(40)
        self.start_btn.setStyleSheet("""
        QPushButton {
            background-color: rgb(58, 110, 165);
            color: white;
            font-weight: bold;
            padding: 8px;
            border-radius: 4px;
            border: 1px solid rgb(40, 80, 120);
        }
        QPushButton:hover {
            background-color: rgb(70, 125, 185);
        }
        QPushButton:pressed {
            background-color: rgb(40, 90, 140);
        }
        QPushButton:disabled {
            background-color: rgb(140, 140, 140);
            color: rgb(220, 220, 220);
        }
        """)
        self.start_btn.clicked.connect(self._start_create)
        root.addWidget(self.start_btn)

        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        root.addWidget(QLabel("Log:"))
        root.addWidget(self.log, 1)

    def _select_output_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Select output folder")
        if folder:
            self.output_folder_input.setText(folder)
            self._save_settings()

    def _start_create(self) -> None:
        output_folder_text = self.output_folder_input.text().strip()
        label = self.label_input.text().strip()
        if not output_folder_text:
            QMessageBox.warning(self, "Missing Folder", "Please select an output folder.")
            return
        if not label:
            QMessageBox.warning(self, "Missing Label", "Please provide a label.")
            return

        output_dir = Path(output_folder_text)
        if not output_dir.exists() or not output_dir.is_dir():
            QMessageBox.warning(self, "Invalid Folder", "Output folder does not exist.")
            return

        output_type = self.output_type_combo.currentText()
        extension = output_type.lower()
        disk_count = self.disk_count_input.value()

        self._set_busy(True)
        try:
            for disk_index in range(1, disk_count + 1):
                if not self._prompt_continue(
                        title="Insert Source Disk",
                        message=f"Insert source floppy for Disk {disk_index} and click Continue.",
                ):
                    self._append_log("Create workflow stopped by user.")
                    return

                output_file = output_dir / f"{label} Disk {disk_index}.{extension}"

                while True:
                    command = build_read_command(
                        output_path=output_file,
                        output_type=output_type,
                        fmt=self._selected_format(),
                        extra_flags=self.extra_flags_input.text(),
                        gw_executable=self._settings.value("app/gw_path", detect_gw_executable(), type=str).strip() or "gw",
                    )
                    result = self._run_command_with_progress(command)
                    if result.cancelled:
                        self._append_log("Create workflow aborted by user during command execution.")
                        return
                    if result.return_code == 0:
                        if self._looks_like_cli_failure(result.output_lines):
                            self._append_log(
                                f"Disk {disk_index}: command output indicates a failure."
                            )
                            action = self._failure_action(disk_index)
                            if action.retry:
                                continue
                            if action.skip:
                                self._append_log(f"Disk {disk_index}: skipped after error.")
                                break
                            if action.abort:
                                self._append_log("Create workflow aborted.")
                                return
                        if not output_file.exists() or output_file.stat().st_size == 0:
                            self._append_log(
                                f"Disk {disk_index}: output image was not created correctly."
                            )
                            action = self._failure_action(disk_index)
                            if action.retry:
                                continue
                            if action.skip:
                                self._append_log(f"Disk {disk_index}: skipped after error.")
                                break
                            if action.abort:
                                self._append_log("Create workflow aborted.")
                                return
                        self._append_log(f"Disk {disk_index}: image created at {output_file}.")
                        break

                    action = self._failure_action(disk_index)
                    if action.retry:
                        continue
                    if action.skip:
                        self._append_log(f"Disk {disk_index}: skipped after error.")
                        break
                    if action.abort:
                        self._append_log("Create workflow aborted.")
                        return
        finally:
            self._set_busy(False)

    def _append_log(self, text: str) -> None:
        self.log.appendPlainText(text)
        self.log.moveCursor(QTextCursor.End)

    def _set_busy(self, busy: bool) -> None:
        self.start_btn.setEnabled(not busy)

    def _run_command_with_progress(self, command: list[str]):
        progress = QProgressDialog("Running gw command...", "Abort", 0, 0, self)
        progress.setWindowTitle("Greaseweazle Running")
        progress.setWindowModality(Qt.ApplicationModal)
        progress.setMinimumDuration(0)

        thread = QThread(self)
        worker = CommandWorker(command)
        worker.moveToThread(thread)

        result_holder: dict[str, object] = {}
        loop = QEventLoop(self)

        worker.output.connect(self._append_log)
        worker.finished.connect(lambda result: result_holder.setdefault("result", result))
        worker.finished.connect(loop.quit)
        thread.started.connect(worker.run)
        progress.canceled.connect(
            lambda: (self._append_log("[abort requested]"), worker.cancel())
        )

        thread.start()
        progress.show()
        loop.exec()

        progress.hide()
        thread.quit()
        thread.wait()

        return result_holder["result"]

    def _looks_like_cli_failure(self, output_lines: list[str] | None) -> bool:
        if not output_lines:
            return False
        error_markers = ("error", "failed", "no flux", "no index", "no disk")
        lowered = " ".join(output_lines).lower()
        return any(marker in lowered for marker in error_markers)

    def _failure_action(self, disk_index: int) -> DiskAction:
        msg = QMessageBox(self)
        msg.setIcon(QMessageBox.Warning)
        msg.setWindowTitle("Command Failed")
        msg.setText(f"Disk {disk_index} failed.")
        retry_btn = msg.addButton("Retry", QMessageBox.AcceptRole)
        skip_btn = msg.addButton("Skip", QMessageBox.DestructiveRole)
        abort_btn = msg.addButton("Abort", QMessageBox.RejectRole)
        msg.exec()
        clicked = msg.clickedButton()
        return DiskAction(
            retry=clicked is retry_btn,
            skip=clicked is skip_btn,
            abort=clicked is abort_btn,
        )

    def _prompt_continue(self, title: str, message: str) -> bool:
        box = QMessageBox(self)
        box.setWindowTitle(title)
        box.setText(message)
        continue_btn = box.addButton("Continue", QMessageBox.AcceptRole)
        cancel_btn = box.addButton("Cancel", QMessageBox.RejectRole)
        box.exec()
        return box.clickedButton() is continue_btn and box.clickedButton() is not cancel_btn

    def _populate_format_combo(self) -> None:
        current_value = self.format_combo.currentText().strip()
        self.format_combo.blockSignals(True)
        self.format_combo.clear()
        self.format_combo.addItems(COMMON_GW_FORMATS)
        if self._all_formats_loaded:
            self.format_combo.insertSeparator(self.format_combo.count())
            for fmt in ALL_GW_FORMATS:
                if fmt not in COMMON_GW_FORMATS:
                    self.format_combo.addItem(fmt)
        else:
            self.format_combo.insertSeparator(self.format_combo.count())
            self.format_combo.addItem(LOAD_MORE_FORMATS_TEXT)

        if current_value and current_value != LOAD_MORE_FORMATS_TEXT:
            index = self.format_combo.findText(current_value)
            if index >= 0:
                self.format_combo.setCurrentIndex(index)
            else:
                default_index = self.format_combo.findText("ibm.1440")
                self.format_combo.setCurrentIndex(default_index if default_index >= 0 else 0)
        else:
            default_index = self.format_combo.findText("ibm.1440")
            self.format_combo.setCurrentIndex(default_index if default_index >= 0 else 0)
        self.format_combo.blockSignals(False)

    def _on_format_changed(self, index: int) -> None:
        if index < 0:
            return
        if self.format_combo.itemText(index) != LOAD_MORE_FORMATS_TEXT:
            return

        previous_format = "ibm.1440"
        current_text = self.format_combo.currentText().strip()
        if current_text and current_text != LOAD_MORE_FORMATS_TEXT:
            previous_format = current_text
        elif index > 0:
            previous_format = self.format_combo.itemText(index - 1)

        self._all_formats_loaded = True
        self._populate_format_combo()
        restored_index = self.format_combo.findText(previous_format)
        if restored_index >= 0:
            self.format_combo.setCurrentIndex(restored_index)

        QTimer.singleShot(0, self.format_combo.showPopup)

    def _on_custom_format_toggled(self, checked: bool) -> None:
        self.format_combo.setEnabled(not checked)
        self.custom_format_input.setEnabled(checked)
        if checked and not self.custom_format_input.text().strip():
            self.custom_format_input.setText(self._selected_dropdown_format())

    def _selected_dropdown_format(self) -> str:
        current_text = self.format_combo.currentText().strip()
        if current_text == LOAD_MORE_FORMATS_TEXT:
            return "ibm.1440"
        return current_text

    def _selected_format(self) -> str:
        if self.custom_format_checkbox.isChecked():
            return self.custom_format_input.text().strip()
        return self._selected_dropdown_format()


def _disk_sort_key(path: Path) -> tuple[int, str]:
    name = path.stem.lower()
    match = re.search(r"(?:disk|disc)?\s*(\d+)", name)
    if match:
        return int(match.group(1)), path.name.lower()
    return 9999, path.name.lower()
