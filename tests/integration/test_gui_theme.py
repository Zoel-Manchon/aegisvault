"""The stylesheet is built from the design tokens, in both modes."""
import importlib
import os
import re

import pytest

from ferrovault.adapters.inbound.gui import theme
from ferrovault.adapters.inbound.gui.design import tokens as t

# Pre-redesign hues that must not survive anywhere in the stylesheet.
OLD_HUES = ("#5B6CFF", "#22D3EE", "#2563EB", "rgba(91, 108, 255", "rgba(34, 211, 238")


@pytest.mark.parametrize("pal", [t.DARK, t.LIGHT], ids=["dark", "light"])
def test_stylesheet_builds_from_palette(pal):
    qss = theme.build_stylesheet(pal)
    assert qss.count("{") == qss.count("}")
    for hue in OLD_HUES:
        assert hue.lower() not in qss.lower()
    for token in ("BG_BASE", "SURFACE_1", "SURFACE_2", "SURFACE_3", "TEXT_PRIMARY", "TEXT_SECONDARY",
                  "ACCENT", "ON_ACCENT", "FOCUS_RING", "SELECTION_BORDER", "BORDER_CONTROL", "DANGER"):
        assert getattr(pal, token) in qss, token


def test_every_colour_in_the_stylesheet_is_a_token():
    for pal in (t.DARK, t.LIGHT):
        allowed = {v.upper() for v in pal.colors().values()}
        used = {c.upper() for c in re.findall(r"#[0-9A-Fa-f]{6}\b", theme.build_stylesheet(pal))}
        assert used <= allowed, sorted(used - allowed)


def test_keyboard_focus_ring_rules_exist():
    qss = theme.build_stylesheet(t.DARK)
    ring = f"{t.FOCUS_RING_W}px solid {t.DARK.FOCUS_RING}"
    for selector in ('QPushButton[focusRing="true"]', 'QLineEdit[focusRing="true"]',
                     'QPushButton#primary[focusRing="true"]', 'QCheckBox[focusRing="true"]::indicator'):
        assert selector in qss
    assert ring in qss


def test_primary_text_uses_on_accent():
    qss = theme.build_stylesheet(t.DARK)
    block = qss[qss.index("QPushButton#primary {"):]
    block = block[:block.index("}")]
    assert f"background: {t.DARK.ACCENT}" in block and f"color: {t.DARK.ON_ACCENT}" in block


def test_mode_comes_from_environment(monkeypatch):
    try:
        monkeypatch.setenv("AEGISVAULT_THEME", "light")
        assert importlib.reload(theme).PALETTE is t.LIGHT
        monkeypatch.setenv("AEGISVAULT_THEME", "sepia")
        assert importlib.reload(theme).PALETTE is t.DARK
    finally:
        monkeypatch.delenv("AEGISVAULT_THEME", raising=False)
        importlib.reload(theme)


def test_focus_ring_filter_marks_keyboard_focus_only():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    pytest.importorskip("PySide6")
    from PySide6.QtCore import QEvent, Qt
    from PySide6.QtGui import QFocusEvent
    from PySide6.QtWidgets import QApplication, QLineEdit

    from ferrovault.adapters.inbound.gui.focus_ring import FocusRingFilter

    app = QApplication.instance() or QApplication([])
    flt = FocusRingFilter(app)
    app.installEventFilter(flt)
    try:
        field = QLineEdit()
        QApplication.sendEvent(field, QFocusEvent(QEvent.Type.FocusIn, Qt.FocusReason.TabFocusReason))
        assert field.property("focusRing") is True
        QApplication.sendEvent(field, QFocusEvent(QEvent.Type.FocusOut, Qt.FocusReason.TabFocusReason))
        assert field.property("focusRing") is False
        QApplication.sendEvent(field, QFocusEvent(QEvent.Type.FocusIn, Qt.FocusReason.MouseFocusReason))
        assert not field.property("focusRing")
    finally:
        app.removeEventFilter(flt)
