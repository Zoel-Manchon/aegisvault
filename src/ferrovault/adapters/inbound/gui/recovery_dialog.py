"""Recovery + rotation dialogs: enrol shares, restore from shares, rotate."""
from __future__ import annotations

from PySide6.QtWidgets import (QDialog, QFormLayout, QHBoxLayout, QLabel,
                               QLineEdit, QMessageBox, QPlainTextEdit,
                               QPushButton, QSpinBox, QVBoxLayout)

from ....application.errors import AuthenticationError
from .theme import ACCENT, DANGER, MUTED


class EnrollDialog(QDialog):
    """Generate K-of-N Shamir recovery shares from inside an unlocked vault."""

    def __init__(self, session, parent=None):
        super().__init__(parent)
        self._session = session
        self.setWindowTitle("Recovery shares")
        self.setMinimumWidth(460)
        layout = QVBoxLayout(self)

        intro = QLabel("Split a recovery key into shares. Any K of N can reset "
                       "your master password if you forget it.")
        intro.setWordWrap(True)
        intro.setObjectName("muted")
        layout.addWidget(intro)

        form = QFormLayout()
        self.n = QSpinBox()
        self.n.setRange(2, 10)
        self.n.setValue(5)
        self.k = QSpinBox()
        self.k.setRange(2, 5)
        self.k.setValue(3)
        self.n.valueChanged.connect(lambda v: self.k.setMaximum(v))
        form.addRow("Total shares (N)", self.n)
        form.addRow("Threshold (K)", self.k)
        layout.addLayout(form)

        gen = QPushButton("Generate shares")
        gen.setObjectName("primary")
        gen.clicked.connect(self._generate)
        layout.addWidget(gen)

        self.output = QPlainTextEdit()
        self.output.setReadOnly(True)
        self.output.setPlaceholderText("shares will appear here")
        layout.addWidget(self.output)

        self.warn = QLabel("")
        self.warn.setWordWrap(True)
        layout.addWidget(self.warn)

    def _generate(self):
        shares = self._session.enroll_recovery(self.n.value(), self.k.value())
        self.output.setPlainText("\n".join(shares))
        self.warn.setText("⚠ Store each share separately. Anyone with "
                          f"{self.k.value()} shares can reset your password.")
        self.warn.setStyleSheet(f"color: {DANGER};")


class RestoreDialog(QDialog):
    """Reset a forgotten master password using recovery shares (pre-unlock)."""

    def __init__(self, service, parent=None):
        super().__init__(parent)
        self._service = service
        self.new_password = None
        self.setWindowTitle("Recover vault")
        self.setMinimumWidth(460)
        layout = QVBoxLayout(self)

        layout.addWidget(QLabel("Paste your recovery shares, one per line:"))
        self.shares = QPlainTextEdit()
        self.shares.setPlaceholderText("1-ab3f…\n3-9c02…\n5-77de…")
        layout.addWidget(self.shares)

        form = QFormLayout()
        self.pw = QLineEdit()
        self.pw.setEchoMode(QLineEdit.Password)
        self.confirm = QLineEdit()
        self.confirm.setEchoMode(QLineEdit.Password)
        form.addRow("New password", self.pw)
        form.addRow("Confirm", self.confirm)
        layout.addLayout(form)

        row = QHBoxLayout()
        row.addStretch()
        cancel = QPushButton("Cancel")
        cancel.clicked.connect(self.reject)
        restore = QPushButton("Restore")
        restore.setObjectName("primary")
        restore.clicked.connect(self._restore)
        row.addWidget(cancel)
        row.addWidget(restore)
        layout.addLayout(row)

    def _restore(self):
        shares = [ln.strip() for ln in self.shares.toPlainText().splitlines()
                  if ln.strip()]
        if not shares:
            QMessageBox.warning(self, "Recover", "Enter your recovery shares.")
            return
        if not self.pw.text() or self.pw.text() != self.confirm.text():
            QMessageBox.warning(self, "Recover", "Passwords are empty or do not match.")
            return
        try:
            self._service.recover(shares, self.pw.text())
        except (AuthenticationError, ValueError) as exc:
            QMessageBox.critical(self, "Recover", f"Recovery failed: {exc}")
            return
        self.new_password = self.pw.text()
        self.accept()


class RotateDialog(QDialog):
    """Change the master password (re-wraps the data key)."""

    def __init__(self, session, parent=None):
        super().__init__(parent)
        self._session = session
        self.setWindowTitle("Change master password")
        self.setMinimumWidth(400)
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.pw = QLineEdit()
        self.pw.setEchoMode(QLineEdit.Password)
        self.confirm = QLineEdit()
        self.confirm.setEchoMode(QLineEdit.Password)
        form.addRow("New password", self.pw)
        form.addRow("Confirm", self.confirm)
        layout.addLayout(form)
        row = QHBoxLayout()
        row.addStretch()
        cancel = QPushButton("Cancel")
        cancel.clicked.connect(self.reject)
        ok = QPushButton("Change")
        ok.setObjectName("primary")
        ok.clicked.connect(self._rotate)
        row.addWidget(cancel)
        row.addWidget(ok)
        layout.addLayout(row)

    def _rotate(self):
        if not self.pw.text() or self.pw.text() != self.confirm.text():
            QMessageBox.warning(self, "Rotate", "Passwords are empty or do not match.")
            return
        self._session.rotate(self.pw.text())
        QMessageBox.information(self, "Rotate", "Master password changed.")
        self.accept()
