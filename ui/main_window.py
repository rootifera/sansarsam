from __future__ import annotations

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from services.greaseweazle import detect_gw_executable
from ui.tabs import ConvertImagesTab, CreateImagesTab, WriteImagesTab


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Sansarsam")
        self.resize(900, 700)

        self._settings = QSettings()

        container = QWidget()
        layout = QVBoxLayout(container)

        gw_row = QHBoxLayout()

        self.gw_input = QLineEdit(
            self._settings.value("app/gw_path", detect_gw_executable(), type=str)
        )
        self.gw_input.textChanged.connect(self._save_gw_path)

        gw_browse_btn = QPushButton("Browse gw")
        gw_browse_btn.clicked.connect(self._select_gw_path)

        gw_row.addWidget(QLabel("gw executable:"))
        gw_row.addWidget(self.gw_input, 1)
        gw_row.addWidget(gw_browse_btn)

        layout.addLayout(gw_row)

        tabs = QTabWidget()
        tabs.addTab(WriteImagesTab(), "Write to Disk")
        tabs.addTab(CreateImagesTab(), "Read from Disk")
        tabs.addTab(ConvertImagesTab(), "Convert Images")

        layout.addWidget(tabs)

        self.setCentralWidget(container)

    def _save_gw_path(self) -> None:
        self._settings.setValue("app/gw_path", self.gw_input.text().strip())

    def _select_gw_path(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Select gw executable")
        if path:
            self.gw_input.setText(path)
