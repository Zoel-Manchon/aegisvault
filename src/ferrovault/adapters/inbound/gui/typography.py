"""Font registration for the desktop app.

Inter ships with the package. The monospace family of the design (JetBrains
Mono) is not bundled, so the stack falls back to Cascadia Code / Consolas,
which Windows already has. The ``offscreen`` platform (headless screenshots
and tests) sees no system fonts at all, so there the Windows ones are
registered explicitly.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

from PySide6.QtGui import QFont, QFontDatabase, QGuiApplication

from .design.tokens import TYPE_BODY

_WINDOWS_FALLBACKS = ("CascadiaMono.ttf", "CascadiaCode.ttf", "consola.ttf", "consolab.ttf", "segoeui.ttf",
                      "segoeuib.ttf", "seguisym.ttf")


def load_fonts(app) -> str:
    """Register the bundled fonts and set the UI font; returns the UI family."""
    family = None
    for ttf in sorted((Path(__file__).parent / "fonts").glob("*.ttf")):
        fid = QFontDatabase.addApplicationFont(str(ttf))
        families = QFontDatabase.applicationFontFamilies(fid)
        if families and family is None:
            family = families[0]
    if QGuiApplication.platformName() == "offscreen" and sys.platform == "win32":
        fonts_dir = Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts"
        for name in _WINDOWS_FALLBACKS:
            candidate = fonts_dir / name
            if candidate.exists():
                QFontDatabase.addApplicationFont(str(candidate))
    font = QFont(family or "Segoe UI")
    font.setPixelSize(TYPE_BODY.size)  # the base size; the stylesheet sets no global font
    font.setHintingPreference(QFont.PreferFullHinting)
    app.setFont(font)
    return family or "Segoe UI"
