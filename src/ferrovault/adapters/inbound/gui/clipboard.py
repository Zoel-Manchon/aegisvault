"""Clipboard handling for secrets.

* On Windows the copy carries the formats that keep it out of clipboard
  history (Win+V), out of cloud clipboard sync and away from clipboard
  monitors: ``ExcludeClipboardContentFromMonitorProcessing``,
  ``CanIncludeInClipboardHistory`` = 0 and ``CanUploadToCloudClipboard`` = 0.
  On macOS and X11/Wayland the usual "concealed"/password-manager hints are
  added instead.
* The clipboard is cleared after the configured delay, on lock and on quit -
  but only if it still holds what AegisVault put there (compared by SHA-256),
  so something the user copied afterwards is never wiped.
"""
from __future__ import annotations

import hashlib
import struct
import sys

from PySide6.QtCore import QByteArray, QMimeData, QObject, QTimer

_DWORD_ZERO = QByteArray(struct.pack("<I", 0))


def _win_format(name: str) -> str:
    # Qt maps this MIME form to a registered Windows clipboard format called ``name``.
    return f'application/x-qt-windows-mime;value="{name}"'


def secret_mime(text: str, exclude_history: bool = True, platform: str | None = None) -> QMimeData:
    """QMimeData for ``text`` with the platform's "do not keep this" markers."""
    platform = platform or sys.platform
    mime = QMimeData()
    mime.setText(text)
    if not exclude_history:
        return mime
    if platform == "win32":
        mime.setData(_win_format("ExcludeClipboardContentFromMonitorProcessing"), QByteArray(b"\x01"))
        mime.setData(_win_format("CanIncludeInClipboardHistory"), _DWORD_ZERO)
        mime.setData(_win_format("CanUploadToCloudClipboard"), _DWORD_ZERO)
    elif platform == "darwin":
        mime.setData("application/x-nspasteboard-concealed-type", QByteArray(b"secret"))
    else:
        mime.setData("x-kde-passwordManagerHint", QByteArray(b"secret"))
    return mime


def _digest(text: str) -> bytes:
    return hashlib.sha256(text.encode("utf-8")).digest()


class SecureClipboard(QObject):
    """Copies secrets and clears them later, but only if they are still there."""

    def __init__(self, clipboard, parent: QObject | None = None):
        super().__init__(parent)
        self._clipboard = clipboard
        self._digest: bytes | None = None
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self.clear_if_ours)

    def copy(self, text: str, clear_after_s: int, exclude_history: bool = True) -> None:
        self._clipboard.setMimeData(secret_mime(text, exclude_history))
        self._digest = _digest(text)
        if clear_after_s > 0:
            self._timer.start(int(clear_after_s * 1000))

    def owns_content(self) -> bool:
        if self._digest is None:
            return False
        try:
            current = self._clipboard.text()
        except RuntimeError:
            return False
        return bool(current) and _digest(current) == self._digest

    def clear_if_ours(self) -> bool:
        """Clear the clipboard if it still holds our copy. Returns True if cleared."""
        self._timer.stop()
        ours = self.owns_content()
        if ours:
            self._clipboard.clear()
        self._digest = None
        return ours

    @property
    def pending(self) -> bool:
        return self._digest is not None
