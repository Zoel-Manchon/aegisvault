"""Lightweight startup/progress surfaces used around expensive GUI phases."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QLabel, QProgressBar, QVBoxLayout

from .branding import PRODUCT_NAME
from .svg import logo_widget


class StartupSplash(QDialog):
    """Small non-modal splash shown after unlock while the workspace loads."""

    def __init__(self, title: str = PRODUCT_NAME, subtitle: str = "Preparing secure workspace…", parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setObjectName("startupSplash")
        self.setWindowFlag(Qt.FramelessWindowHint, True)
        self.setModal(False)
        self.setFixedWidth(420)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 26, 28, 26)
        layout.setSpacing(14)
        layout.addWidget(logo_widget(54), alignment=Qt.AlignHCenter)

        self.title = QLabel(title)
        self.title.setObjectName("splashTitle")
        self.title.setAlignment(Qt.AlignHCenter)
        layout.addWidget(self.title)

        self.status = QLabel(subtitle)
        self.status.setObjectName("splashStatus")
        self.status.setAlignment(Qt.AlignHCenter)
        self.status.setWordWrap(True)
        layout.addWidget(self.status)

        self.progress = QProgressBar()
        self.progress.setObjectName("splashProgress")
        self.progress.setRange(0, 0)
        self.progress.setTextVisible(False)
        layout.addWidget(self.progress)

    def set_status(self, text: str) -> None:
        self.status.setText(text)
