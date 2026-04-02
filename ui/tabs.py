from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re

from PySide6.QtCore import Qt
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
    QPlainTextEdit,
    QSpinBox,
    QVBoxLayout,
    QWidget,
    QFileDialog,
)

from services.greaseweazle import build_read_command, build_write_command, run_command

SUPPORTED_IMAGE_SUFFIXES = {".img", ".ima", ".scp", ".raw"}


@dataclass
class DiskAction:
    retry: bool = False
    skip: bool = False
    abort: bool = False


class WriteImagesTab(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self._build_ui()

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
        move_up_btn.clicked.connect(self._move_selected_up)
        move_down_btn.clicked.connect(self._move_selected_down)
        reorder_buttons.addWidget(move_up_btn)
        reorder_buttons.addWidget(move_down_btn)
        reorder_buttons.addStretch(1)
        layout.addLayout(reorder_buttons)

        options_group = QGroupBox("Options")
        options_layout = QFormLayout(options_group)
        self.format_input = QLineEdit("ibm.1440")
        self.verify_checkbox = QCheckBox("Verify")
        self.verify_checkbox.setChecked(True)
        self.extra_flags_input = QLineEdit()
        options_layout.addRow("Format:", self.format_input)
        options_layout.addRow("Verify:", self.verify_checkbox)
        options_layout.addRow("Extra flags:", self.extra_flags_input)
        layout.addWidget(options_group)

        self.start_btn = QPushButton("Start")
        self.start_btn.clicked.connect(self._start_write)
        layout.addWidget(self.start_btn)

        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        layout.addWidget(QLabel("Log:"))
        layout.addWidget(self.log, 1)

    def _select_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Select image folder")
        if folder:
            self.folder_input.setText(folder)

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
        sorted_files = sorted(found, key=_disk_sort_key)

        self.file_list.clear()
        for file_path in sorted_files:
            item = QListWidgetItem(file_path.name)
            item.setData(Qt.UserRole, str(file_path))
            self.file_list.addItem(item)

        self._append_log(f"Found {len(sorted_files)} supported image file(s).")

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
                        fmt=self.format_input.text(),
                        verify=self.verify_checkbox.isChecked(),
                        extra_flags=self.extra_flags_input.text(),
                    )
                    result = run_command(command, self._append_log)
                    if result.return_code == 0:
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

    def _collect_disk_files(self) -> list[Path]:
        files: list[Path] = []
        for index in range(self.file_list.count()):
            item = self.file_list.item(index)
            path_value = item.data(Qt.UserRole)
            if path_value:
                files.append(Path(path_value))
        return files

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
        cursor = self.log.textCursor()
        cursor.movePosition(cursor.End)
        self.log.setTextCursor(cursor)

    def _set_busy(self, busy: bool) -> None:
        self.start_btn.setEnabled(not busy)

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


class CreateImagesTab(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self._build_ui()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)

        destination_row = QHBoxLayout()
        self.output_folder_input = QLineEdit()
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
        self.disk_count_input = QSpinBox()
        self.disk_count_input.setMinimum(1)
        self.disk_count_input.setValue(1)

        self.output_type_combo = QComboBox()
        self.output_type_combo.addItems(["IMG", "SCP"])

        self.format_input = QLineEdit("ibm.1440")
        self.extra_flags_input = QLineEdit()

        details_layout.addWidget(QLabel("Label:"), 0, 0)
        details_layout.addWidget(self.label_input, 0, 1)
        details_layout.addWidget(QLabel("Total disks:"), 1, 0)
        details_layout.addWidget(self.disk_count_input, 1, 1)
        details_layout.addWidget(QLabel("Output type:"), 2, 0)
        details_layout.addWidget(self.output_type_combo, 2, 1)
        details_layout.addWidget(QLabel("Format (IMG):"), 3, 0)
        details_layout.addWidget(self.format_input, 3, 1)
        details_layout.addWidget(QLabel("Extra flags:"), 4, 0)
        details_layout.addWidget(self.extra_flags_input, 4, 1)

        root.addWidget(details_group)

        self.start_btn = QPushButton("Start")
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
                        fmt=self.format_input.text(),
                        extra_flags=self.extra_flags_input.text(),
                    )
                    result = run_command(command, self._append_log)
                    if result.return_code == 0:
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
        cursor = self.log.textCursor()
        cursor.movePosition(cursor.End)
        self.log.setTextCursor(cursor)

    def _set_busy(self, busy: bool) -> None:
        self.start_btn.setEnabled(not busy)

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


def _disk_sort_key(path: Path) -> tuple[int, str]:
    name = path.stem.lower()
    match = re.search(r"(?:disk|disc)?\s*(\d+)", name)
    if match:
        return int(match.group(1)), path.name.lower()
    return 9999, path.name.lower()
