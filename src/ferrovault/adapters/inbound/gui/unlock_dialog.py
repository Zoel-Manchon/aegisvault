"""Unlock / create-vault dialog - the first screen."""
from __future__ import annotations

from PySide6.QtCore import QThread, Qt, QTimer
from PySide6.QtWidgets import (QDialog, QLabel, QLineEdit, QMessageBox,
                               QProgressBar, QPushButton, QVBoxLayout)

from .async_unlock import VaultUnlockWorker
from .branding import PRODUCT_NAME
from .svg import logo_widget


class UnlockDialog(QDialog):
    """Returns a VaultSession via ``self.session`` on success.

    The expensive password KDF/decryption path runs on a worker thread so the
    dialog can keep repainting and show an indeterminate progress state.
    """

    def __init__(self, service, vault_path: str, parent=None, profiler=None):
        # `service` may be a VaultService or a zero-arg factory returning one.
        # A factory lets the window paint before the crypto stack imports.
        super().__init__(parent)
        import os
        self._service_or_factory = service
        self._service_cache = None
        self._exists = os.path.exists(vault_path)
        self._profiler = profiler
        self._thread: QThread | None = None
        self._worker: VaultUnlockWorker | None = None
        self._busy = False
        self.session = None

        self.setWindowTitle(PRODUCT_NAME)
        self.setMinimumWidth(420)
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(28, 28, 28, 28)

        logo = logo_widget(72)
        layout.addWidget(logo, alignment=Qt.AlignHCenter)

        title = QLabel(PRODUCT_NAME)
        title.setObjectName("brand")
        title.setAlignment(Qt.AlignHCenter)
        layout.addWidget(title)

        sub = QLabel(("Unlock vault" if self._exists else "Create a new vault")
                     + f"\n{vault_path}")
        sub.setObjectName("muted")
        sub.setAlignment(Qt.AlignHCenter)
        layout.addWidget(sub)

        self.password = QLineEdit()
        self.password.setEchoMode(QLineEdit.Password)
        self.password.setPlaceholderText("master password")
        layout.addWidget(self.password)

        self.confirm = QLineEdit()
        self.confirm.setEchoMode(QLineEdit.Password)
        self.confirm.setPlaceholderText("confirm password")
        self.confirm.setVisible(not self._exists)
        layout.addWidget(self.confirm)

        self.status = QLabel("Ready")
        self.status.setObjectName("unlockStatus")
        self.status.setAlignment(Qt.AlignHCenter)
        self.status.setVisible(False)
        layout.addWidget(self.status)

        self.progress = QProgressBar()
        self.progress.setObjectName("unlockProgress")
        self.progress.setRange(0, 0)
        self.progress.setTextVisible(False)
        self.progress.setVisible(False)
        layout.addWidget(self.progress)

        self.submit_btn = QPushButton("Unlock" if self._exists else "Create vault")
        self.submit_btn.setObjectName("primary")
        self.submit_btn.clicked.connect(self._submit)
        layout.addWidget(self.submit_btn)

        self.recover_btn: QPushButton | None = None
        if self._exists:
            self.recover_btn = QPushButton("Forgot password? Recover with shares")
            self.recover_btn.setObjectName("ghost")
            self.recover_btn.clicked.connect(self._recover)
            layout.addWidget(self.recover_btn)

        self.password.returnPressed.connect(self._submit)
        self.confirm.returnPressed.connect(self._submit)
        QTimer.singleShot(0, self.password.setFocus)

    @property
    def _service(self):
        if self._service_cache is None:
            s = self._service_or_factory
            self._service_cache = s() if callable(s) else s
        return self._service_cache

    def reject(self) -> None:
        if self._busy:
            return
        super().reject()

    def _recover(self):
        if self._busy:
            return
        from .recovery_dialog import RestoreDialog
        dlg = RestoreDialog(self._service, self)
        if dlg.exec() and dlg.new_password:
            self._start_unlock(dlg.new_password, create=False,
                               message="Recovery complete. Opening recovered vault…")

    def _submit(self):
        if self._busy:
            return
        pw = self.password.text()
        if not pw:
            return
        if not self._exists and pw != self.confirm.text():
            QMessageBox.warning(self, PRODUCT_NAME, "Passwords do not match.")
            return
        self._start_unlock(
            pw,
            create=not self._exists,
            message=("Creating encrypted vault…" if not self._exists else "Deriving key and decrypting vault…"),
        )

    def _start_unlock(self, password: str, *, create: bool, message: str) -> None:
        self._set_busy(True, message)
        if self._profiler:
            self._profiler.mark("unlock-started")

        self._thread = QThread(self)
        self._worker = VaultUnlockWorker(self._service, password, create=create)
        self._worker.moveToThread(self._thread)

        self._thread.started.connect(self._worker.run)
        self._worker.succeeded.connect(self._on_unlock_succeeded)
        self._worker.authentication_failed.connect(self._on_auth_failed)
        self._worker.failed.connect(self._on_unlock_failed)
        self._worker.succeeded.connect(self._thread.quit)
        self._worker.authentication_failed.connect(self._thread.quit)
        self._worker.failed.connect(self._thread.quit)
        self._thread.finished.connect(self._worker.deleteLater)
        self._thread.finished.connect(self._thread.deleteLater)
        self._thread.finished.connect(self._clear_worker_refs)
        self._thread.start()

    def _set_busy(self, busy: bool, message: str = "") -> None:
        self._busy = busy
        self.password.setEnabled(not busy)
        self.confirm.setEnabled(not busy)
        self.submit_btn.setEnabled(not busy)
        if self.recover_btn is not None:
            self.recover_btn.setEnabled(not busy)
        self.status.setVisible(busy or bool(message))
        self.progress.setVisible(busy)
        self.status.setText(message or "Ready")
        if busy:
            self.submit_btn.setText("Opening…")
        else:
            self.submit_btn.setText("Unlock" if self._exists else "Create vault")

    def _on_unlock_succeeded(self, session) -> None:
        self.session = session
        if self._profiler:
            self._profiler.mark("unlock-finished")
        self.status.setText("Vault unlocked. Loading workspace…")
        self.accept()

    def _on_auth_failed(self, message: str) -> None:
        if self._profiler:
            self._profiler.mark("unlock-failed")
        self._set_busy(False, "")
        QMessageBox.critical(self, PRODUCT_NAME, message)
        self.password.clear()
        self.password.setFocus()

    def _on_unlock_failed(self, summary: str, details: str) -> None:
        if self._profiler:
            self._profiler.mark("unlock-error")
        self._set_busy(False, "")
        QMessageBox.critical(self, PRODUCT_NAME, f"Could not open the vault.\n\n{summary}")
        print(details, flush=True)
        self.password.setFocus()

    def _clear_worker_refs(self) -> None:
        self._worker = None
        self._thread = None
