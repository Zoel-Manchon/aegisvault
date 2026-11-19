"""Keyboard-only focus ring for Qt Widgets.

QSS has ``:focus`` but no ``:focus-visible``: a ring on every mouse click is
noise, and no ring at all fails keyboard users. This application-wide event
filter sets the dynamic property ``focusRing=true`` when a widget receives focus
from the keyboard (Tab, Shift+Tab, a shortcut) and clears it on focus-out. The
stylesheet draws ``[focusRing="true"]`` as a 2 px FOCUS_RING border.
"""
from __future__ import annotations

from PySide6.QtCore import QEvent, QObject, Qt
from PySide6.QtWidgets import QWidget

PROPERTY = "focusRing"
_KEYBOARD_REASONS = frozenset({
    Qt.FocusReason.TabFocusReason,
    Qt.FocusReason.BacktabFocusReason,
    Qt.FocusReason.ShortcutFocusReason,
})


def set_focus_ring(widget: QWidget, on: bool) -> None:
    """Toggle the property and re-polish so the stylesheet picks it up."""
    if bool(widget.property(PROPERTY)) == on:
        return
    widget.setProperty(PROPERTY, on)
    style = widget.style()
    style.unpolish(widget)
    style.polish(widget)
    widget.update()


class FocusRingFilter(QObject):
    """Install once on the QApplication: ``app.installEventFilter(FocusRingFilter(app))``."""

    def eventFilter(self, obj, event):  # noqa: N802 - Qt API name
        kind = event.type()
        if kind == QEvent.Type.FocusIn and isinstance(obj, QWidget):
            set_focus_ring(obj, event.reason() in _KEYBOARD_REASONS)
        elif kind == QEvent.Type.FocusOut and isinstance(obj, QWidget):
            set_focus_ring(obj, False)
        return False
