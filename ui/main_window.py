from __future__ import annotations

from PySide6.QtWidgets import QMainWindow, QTabWidget

from ui.tabs import CreateImagesTab, WriteImagesTab


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Sansarsam")
        self.resize(900, 700)

        tabs = QTabWidget()
        tabs.addTab(WriteImagesTab(), "Write to Disk")
        tabs.addTab(CreateImagesTab(), "Read from Disk")

        self.setCentralWidget(tabs)
