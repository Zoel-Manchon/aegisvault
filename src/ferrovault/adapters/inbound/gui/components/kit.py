"""Component kit of the "Tinta y marfil" redesign (boards 04 and 05).

Small, composable QtWidgets pieces that every screen builds on: text roles,
buttons with keyboard hints, badges and pills that pair colour with an icon or
a word, segmented controls, switches, strength meter, banners, toasts, rings,
spinners, empty states and the frameless dialog frame with its scrim.

Colours come from ``theme.PALETTE`` and the stylesheet in ``theme.py``; this
module only sets object names and dynamic properties, except for the few
widgets that paint themselves (switch, rings, spinner, meter).
"""
from __future__ import annotations

from collections.abc import Callable, Iterable

from PySide6.QtCore import QEvent, QPoint, QRect, QRectF, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QFontDatabase, QFontMetrics, QKeySequence, QPainter, QPen, QShortcut
from PySide6.QtWidgets import (
    QAbstractButton, QButtonGroup, QDialog, QFrame, QGraphicsDropShadowEffect, QHBoxLayout, QLabel, QLayout,
    QLineEdit, QProgressBar, QPushButton, QScrollArea, QSizePolicy, QVBoxLayout, QWidget,
)

from ..design.tokens import ELEVATION_2, ELEVATION_3, FONT_MONO, FONT_UI
from ..icons import icon, pixmap
from ..theme import PALETTE as P

TONE_ICON = {"success": "check", "warning": "warning", "danger": "alert", "info": "info"}


def tone_color(tone: str) -> str:
    return {"success": P.SUCCESS, "warning": P.WARNING, "danger": P.DANGER, "info": P.INFO,
            "accent": P.ACCENT, "muted": P.TEXT_TERTIARY}.get(tone, P.TEXT_SECONDARY)


# ---- small helpers -----------------------------------------------------------
def repolish(widget: QWidget) -> None:
    """Re-apply the stylesheet after a dynamic property changed (widget and children)."""
    for w in [widget, *widget.findChildren(QWidget)]:
        style = w.style()
        style.unpolish(w)
        style.polish(w)
        w.update()


def set_prop(widget: QWidget, name: str, value) -> None:
    if widget.property(name) != value:
        widget.setProperty(name, value)
        repolish(widget)


def clear_layout(layout) -> None:
    while layout is not None and layout.count():
        item = layout.takeAt(0)
        widget = item.widget()
        child = item.layout()
        if widget is not None:
            widget.setParent(None)
            widget.deleteLater()
        elif child is not None:
            clear_layout(child)


def label(text: str = "", role: str = "body", *, wrap: bool = False, selectable: bool = False,
          align=None, tone: str | None = None) -> QLabel:
    lbl = QLabel(text)
    lbl.setObjectName(role)
    if tone:
        lbl.setProperty("tone", tone)
    if wrap:
        lbl.setWordWrap(True)
    if selectable:
        lbl.setTextInteractionFlags(Qt.TextSelectableByMouse)
    if align is not None:
        lbl.setAlignment(align)
    return lbl


def overline(text: str) -> QLabel:
    return label(text.upper(), "overline")


def icon_label(name: str, color: str | None = None, size: int = 16) -> QLabel:
    lbl = QLabel()
    lbl.setPixmap(pixmap(name, color or P.TEXT_SECONDARY, size))
    lbl.setFixedSize(size, size)
    lbl.setStyleSheet("background: transparent;")
    return lbl


def hline() -> QFrame:
    line = QFrame()
    line.setObjectName("hairline")
    return line


def vline() -> QFrame:
    line = QFrame()
    line.setObjectName("vline")
    return line


def hbox(*items, spacing: int = 8, margins=(0, 0, 0, 0)) -> QHBoxLayout:
    box = QHBoxLayout()
    box.setSpacing(spacing)
    box.setContentsMargins(*margins)
    for item in items:
        _add(box, item)
    return box


def vbox(*items, spacing: int = 8, margins=(0, 0, 0, 0)) -> QVBoxLayout:
    box = QVBoxLayout()
    box.setSpacing(spacing)
    box.setContentsMargins(*margins)
    for item in items:
        _add(box, item)
    return box


def _add(box, item) -> None:
    if item is None:
        return
    if item == "stretch":
        box.addStretch(1)
    elif isinstance(item, int):
        box.addSpacing(item)
    elif isinstance(item, QWidget):
        box.addWidget(item)
    else:
        box.addLayout(item)


def wrap_widget(layout, name: str = "transparent") -> QWidget:
    w = QWidget()
    w.setObjectName(name)
    w.setLayout(layout)
    return w


def elide(text: str, font: QFont, width: int, mode=Qt.ElideRight) -> str:
    return QFontMetrics(font).elidedText(text, mode, max(0, width))


def letter_of(name: str) -> str:
    for ch in name or "":
        if ch.isalnum():
            return ch.upper()
    return "·"


_MONO_FAMILIES = (FONT_MONO, "Cascadia Mono", "Cascadia Code", "Consolas", "Courier New")
_mono_resolved: list[str] = []


def mono_family() -> str:
    """First installed family of the monospace stack.

    JetBrains Mono (the design's choice) is not bundled, and Qt does not walk a
    QFont family list when the first name is missing, so resolve it here once.
    """
    if _mono_resolved:
        return _mono_resolved[0]
    available = set(QFontDatabase.families())
    for name in _MONO_FAMILIES:
        if name in available:
            _mono_resolved.append(name)
            return name
    return QFontDatabase.systemFont(QFontDatabase.FixedFont).family()


def mono_font(size: int = 13, weight: int = 400) -> QFont:
    font = QFont(mono_family())
    font.setStyleHint(QFont.Monospace)
    font.setFixedPitch(True)
    font.setPixelSize(size)
    font.setWeight(QFont.Weight(weight))
    return font


def ui_font(size: int = 14, weight: int = 400) -> QFont:
    font = QFont(FONT_UI)
    font.setFamilies([FONT_UI, "Segoe UI Variable", "Segoe UI", "Arial"])
    font.setPixelSize(size)
    font.setWeight(QFont.Weight(weight))
    return font


def group_code(code: str) -> str:
    """'866273' -> '866 273' (TOTP codes and similar)."""
    code = "".join(code.split())
    if len(code) in (6, 8):
        half = len(code) // 2
        return f"{code[:half]} {code[half:]}"
    return code


# ---- text-ish widgets --------------------------------------------------------
class Kbd(QLabel):
    """Keyboard hint chip, e.g. ``Ctrl K``."""

    def __init__(self, text: str, on_accent: bool = False):
        super().__init__(text)
        self.setObjectName("kbd")
        if on_accent:
            self.setProperty("onAccent", True)
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)


class Avatar(QLabel):
    """Letter tile standing in for a site icon (favicons stay offline)."""

    SIZES = {"sm": 24, "md": 36, "lg": 56}

    def __init__(self, name: str = "", size: str = "md", muted: bool = False):
        super().__init__(letter_of(name))
        self.setObjectName("avatar")
        self.setProperty("size", size)
        if muted:
            self.setProperty("muted", True)
        side = self.SIZES.get(size, 36)
        self.setFixedSize(side, side)
        self.setAlignment(Qt.AlignCenter)

    def set_name(self, name: str, muted: bool = False) -> None:
        self.setText(letter_of(name))
        set_prop(self, "muted", bool(muted))


class IconTile(QLabel):
    """Square tile with a centred icon (dialog headers, empty states)."""

    def __init__(self, name: str, tone: str | None = None, size: int = 36, icon_size: int = 18,
                 dashed: bool = False, color: str | None = None):
        super().__init__()
        self.setObjectName("iconTile")
        if tone:
            self.setProperty("tone", tone)
        if dashed:
            self.setProperty("dashed", True)
        self.setFixedSize(size, size)
        self.setAlignment(Qt.AlignCenter)
        self.setPixmap(pixmap(name, color or (tone_color(tone) if tone else P.TEXT_PRIMARY), icon_size))


class Badge(QFrame):
    """22 px badge: optional icon + word. Tones: neutral, success, warning, danger, info, mono, dashed."""

    def __init__(self, text: str, tone: str = "neutral", icon_name: str | None = None):
        super().__init__()
        self.setObjectName("badge")
        self.setFixedHeight(22)
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        row = QHBoxLayout(self)
        row.setContentsMargins(6, 0, 7, 0)
        row.setSpacing(4)
        self._icon = QLabel()
        self._icon.setFixedSize(12, 12)
        self._text = QLabel()
        row.addWidget(self._icon)
        row.addWidget(self._text)
        self.set(text, tone, icon_name)

    def set(self, text: str, tone: str = "neutral", icon_name: str | None = None) -> None:
        self.setProperty("tone", tone)
        self._text.setText(text)
        name = icon_name if icon_name is not None else TONE_ICON.get(tone)
        if name:
            self._icon.setPixmap(pixmap(name, tone_color(tone), 12, 2.0))
            self._icon.show()
        else:
            self._icon.hide()
        repolish(self)


class Chip(QFrame):
    """Pill with an optional icon (category chip, recipient, filter)."""

    removed = Signal()

    def __init__(self, text: str, icon_name: str | None = None, tone: str | None = None,
                 removable: bool = False):
        super().__init__()
        self.setObjectName("chip")
        if tone:
            self.setProperty("tone", tone)
        self.setFixedHeight(26)
        row = QHBoxLayout(self)
        row.setContentsMargins(9, 0, 9 if not removable else 4, 0)
        row.setSpacing(6)
        if icon_name:
            row.addWidget(icon_label(icon_name, tone_color(tone) if tone else P.TEXT_SECONDARY, 14))
        self.text = QLabel(text)
        row.addWidget(self.text)
        if removable:
            close = QPushButton()
            close.setObjectName("iconBtn")
            close.setIcon(icon("close", P.TEXT_SECONDARY, 12))
            close.setIconSize(QSize(12, 12))
            close.setFixedSize(20, 20)
            close.setStyleSheet("padding: 0; min-height: 0; min-width: 0;")
            close.setToolTip("Quitar")
            close.clicked.connect(self.removed.emit)
            row.addWidget(close)


class LockPill(QFrame):
    """"Desbloqueada · bloqueo en 4:41" in the top bar."""

    def __init__(self):
        super().__init__()
        self.setObjectName("lockPill")
        self.setFixedHeight(32)
        row = QHBoxLayout(self)
        row.setContentsMargins(10, 0, 12, 0)
        row.setSpacing(5)
        self._icon = QLabel()
        self._icon.setFixedSize(14, 14)
        self._text = QLabel()
        self._time = QLabel()
        self._time.setObjectName("lockTime")
        row.addWidget(self._icon)
        row.addWidget(self._text)
        row.addWidget(self._time)
        self.setAccessibleName("Estado de la bóveda")

    def set_remaining(self, seconds: int | None, warn_below: int = 60) -> None:
        if seconds is None:
            tone, text, time_text = "warning", "Desbloqueada · sin bloqueo automático", ""
        else:
            tone = "warning" if seconds <= warn_below else "success"
            text = "Desbloqueada · bloqueo en"
            time_text = f"{seconds // 60}:{seconds % 60:02d}"
        self._text.setText(text)
        self._time.setText(time_text)
        self._time.setVisible(bool(time_text))
        if self.property("tone") != tone:
            self._icon.setPixmap(pixmap("unlock", tone_color(tone), 14))
            set_prop(self, "tone", tone)
        self.setToolTip("La clave sale de la memoria al bloquear")


# ---- buttons -----------------------------------------------------------------
_BUTTON_NAMES = {"primary": "primary", "secondary": "", "ghost": "ghost", "danger": "danger",
                 "dangerSolid": "dangerSolid", "link": "link", "icon": "iconBtn", "dropdown": "dropdown",
                 "banner": "bannerAction", "nav": "topNav", "search": "searchTrigger"}


def _icon_color(kind: str) -> str:
    return {"primary": P.ON_ACCENT, "dangerSolid": P.ON_DANGER_SOLID, "danger": P.DANGER,
            "search": P.TEXT_TERTIARY}.get(kind, P.TEXT_PRIMARY)


class Button(QPushButton):
    """QPushButton with the kit's look: kind, leading icon and an optional key hint."""

    def __init__(self, text: str = "", kind: str = "secondary", icon_name: str | None = None,
                 shortcut: str | None = None, size: str = "md", tooltip: str | None = None,
                 on_click: Callable | None = None, icon_size: int = 16, trailing_icon: str | None = None):
        super().__init__()
        self.kind = kind
        name = _BUTTON_NAMES.get(kind, "")
        if name:
            self.setObjectName(name)
        if size != "md":
            self.setProperty("size", size)
        self.setCursor(Qt.PointingHandCursor)
        self._icon_name = icon_name
        self._icon_size = icon_size
        self._kbd = None
        if shortcut or trailing_icon:
            # Text, icon and hint live in an inner row so the hint sits after the text.
            self._row = QHBoxLayout(self)
            pad = 10 if kind == "dropdown" else 14
            self._row.setContentsMargins(pad, 0, pad, 0)
            self._row.setSpacing(6 if kind == "dropdown" else 8)
            self._row.addStretch(1)
            self._lead = QLabel()
            self._lead.setStyleSheet("background: transparent;")
            if icon_name:
                self._lead.setPixmap(pixmap(icon_name, _icon_color(kind), icon_size))
            else:
                self._lead.hide()
            self._text = QLabel(text)
            self._text.setStyleSheet(
                f"background: transparent; color: {_icon_color(kind)}; font-weight: {600 if kind == 'primary' else 500};"
                f" font-size: {15 if size == 'lg' else 13}px;")
            self._row.addWidget(self._lead)
            self._row.addWidget(self._text)
            if shortcut:
                self._kbd = Kbd(shortcut, on_accent=(kind == "primary"))
                self._row.addWidget(self._kbd)
            if trailing_icon:
                self._row.addWidget(icon_label(trailing_icon, _icon_color(kind), 14))
            self._row.addStretch(1)
            for child in (self._lead, self._text):
                child.setAttribute(Qt.WA_TransparentForMouseEvents)
            hint = self._row.sizeHint()
            self.setMinimumWidth(hint.width() + 4)
            self.accessible_text = text
            self.setAccessibleName(text)
        else:
            self._text = None
            self.setText(text)
            if icon_name:
                self.setIcon(icon(icon_name, _icon_color(kind), icon_size))
                self.setIconSize(QSize(icon_size, icon_size))
        if tooltip:
            self.setToolTip(tooltip)
        if on_click is not None:
            self.clicked.connect(lambda _=False: on_click())

    def set_label(self, text: str) -> None:
        if self._text is not None:
            self._text.setText(text)
            self.setAccessibleName(text)
            self.setMinimumWidth(self._row.sizeHint().width() + 4)  # shrink or grow with the text
        else:
            self.setText(text)

    def label_text(self) -> str:
        return self._text.text() if self._text is not None else self.text()

    def set_icon_name(self, name: str, color: str | None = None) -> None:
        self._icon_name = name
        if self._text is not None:
            self._lead.setPixmap(pixmap(name, color or _icon_color(self.kind), self._icon_size))
            self._lead.show()
        else:
            self.setIcon(icon(name, color or _icon_color(self.kind), self._icon_size))


def icon_button(name: str, tooltip: str, on_click: Callable | None = None, size: int = 18,
                color: str | None = None, checkable: bool = False) -> QPushButton:
    btn = QPushButton()
    btn.setObjectName("iconBtn")
    btn.setIcon(icon(name, color or P.TEXT_SECONDARY, size))
    btn.setIconSize(QSize(size, size))
    btn.setToolTip(tooltip)
    btn.setAccessibleName(tooltip)
    btn.setCursor(Qt.PointingHandCursor)
    btn.setCheckable(checkable)
    if on_click is not None:
        btn.clicked.connect(lambda _=False: on_click())
    return btn


class Segmented(QFrame):
    """Exclusive options in one frame. ``accent=True`` fills the choice with ivory."""

    changed = Signal(str)

    def __init__(self, options: Iterable[tuple[str, str]], value: str | None = None, *,
                 accent: bool = False, icons: dict | None = None, expand: bool = True, check_mark: bool = False):
        super().__init__()
        self.setObjectName("segmented")
        if accent:
            self.setProperty("accent", True)
        self._group = QButtonGroup(self)
        self._group.setExclusive(True)
        self._buttons: dict[str, QPushButton] = {}
        self._icons = icons or {}
        self._accent = accent
        self._check = check_mark
        row = QHBoxLayout(self)
        row.setContentsMargins(3, 3, 3, 3)
        row.setSpacing(2)
        for key, text in options:
            btn = QPushButton(text)
            btn.setObjectName("segment")
            btn.setCheckable(True)
            btn.setCursor(Qt.PointingHandCursor)
            if expand:
                btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            self._group.addButton(btn)
            self._buttons[key] = btn
            btn.toggled.connect(lambda on, k=key: self._on_toggled(k, on))
            row.addWidget(btn)
        first = next(iter(self._buttons), None)
        self.set_value(value if value in self._buttons else first, emit=False)

    def _paint_icon(self, key: str, checked: bool) -> None:
        btn = self._buttons[key]
        name = "check" if (self._check and checked) else self._icons.get(key)
        if name:
            color = P.ON_ACCENT if (checked and self._accent) else (P.TEXT_PRIMARY if checked else P.TEXT_SECONDARY)
            btn.setIcon(icon(name, color, 14))
        else:
            btn.setIcon(icon("none"))

    def _on_toggled(self, key: str, on: bool) -> None:
        self._paint_icon(key, on)
        if on:
            self.changed.emit(key)

    def value(self) -> str | None:
        for key, btn in self._buttons.items():
            if btn.isChecked():
                return key
        return None

    def set_value(self, key: str | None, emit: bool = True) -> None:
        if key not in self._buttons:
            return
        if not emit:
            self._group.blockSignals(True)
            for k, b in self._buttons.items():
                b.blockSignals(True)
                b.setChecked(k == key)
                b.blockSignals(False)
                self._paint_icon(k, k == key)
            self._group.blockSignals(False)
        else:
            self._buttons[key].setChecked(True)

    def button(self, key: str) -> QPushButton:
        return self._buttons[key]


class Switch(QAbstractButton):
    """The toggle of board 04: 36x20 track, knob with a check when on."""

    def __init__(self, checked: bool = False):
        super().__init__()
        self.setCheckable(True)
        self.setChecked(checked)
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedSize(40, 22)
        self.setFocusPolicy(Qt.StrongFocus)

    def sizeHint(self) -> QSize:  # noqa: N802 - Qt API
        return QSize(40, 22)

    def paintEvent(self, _event):  # noqa: N802 - Qt API
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        on = self.isChecked()
        enabled = self.isEnabled()
        track = QRectF(1, 1, self.width() - 2, self.height() - 2)
        radius = track.height() / 2
        if on:
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(P.ACCENT if enabled else P.SURFACE_3))
        else:
            p.setPen(QPen(QColor(P.BORDER_CONTROL if enabled else P.BORDER_DEFAULT), 1))
            p.setBrush(QColor(P.SURFACE_2))
        p.drawRoundedRect(track, radius, radius)
        d = track.height() - 6
        x = track.right() - d - 3 if on else track.left() + 3
        knob = QRectF(x, track.top() + 3, d, d)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(P.ON_ACCENT if on else (P.TEXT_SECONDARY if enabled else P.TEXT_DISABLED)))
        p.drawEllipse(knob)
        if on:
            p.drawPixmap(knob.adjusted(3, 3, -3, -3).toRect(), pixmap("check", P.ACCENT, int(d - 6), 3.0))
        if self.property("focusRing"):
            p.setPen(QPen(QColor(P.FOCUS_RING), 2))
            p.setBrush(Qt.NoBrush)
            p.drawRoundedRect(QRectF(1, 1, self.width() - 2, self.height() - 2), radius, radius)
        p.end()


class Toggle(QWidget):
    """Switch + "Sí"/"No" word, as in the settings board."""

    toggled = Signal(bool)

    def __init__(self, checked: bool = False, on_text: str = "Sí", off_text: str = "No"):
        super().__init__()
        self._on, self._off = on_text, off_text
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(8)
        self.switch = Switch(checked)
        self._word = label("", "secondary")
        self._word.setMinimumWidth(22)
        row.addWidget(self.switch)
        row.addWidget(self._word)
        self.switch.toggled.connect(self._changed)
        self._changed(checked, emit=False)

    def _changed(self, on: bool, emit: bool = True) -> None:
        self._word.setText(self._on if on else self._off)
        self.switch.setAccessibleName(self._on if on else self._off)
        if emit:
            self.toggled.emit(on)

    def isChecked(self) -> bool:  # noqa: N802 - Qt naming
        return self.switch.isChecked()

    def setChecked(self, on: bool) -> None:  # noqa: N802 - Qt naming
        self.switch.setChecked(on)

    def setEnabled(self, on: bool) -> None:  # noqa: N802 - Qt naming
        super().setEnabled(on)
        self.switch.setEnabled(on)


# ---- fields -------------------------------------------------------------------
class Field(QLineEdit):
    """QLineEdit with an optional trailing note (e.g. "✓ Coinciden") or key hint."""

    def __init__(self, text: str = "", placeholder: str = "", mono: bool = False):
        super().__init__(text)
        if placeholder:
            self.setPlaceholderText(placeholder)
        if mono:
            self.setObjectName("mono")
        self._trail = QWidget(self)
        self._trail.setAttribute(Qt.WA_TransparentForMouseEvents)
        self._trail.setStyleSheet("background: transparent;")
        trail_row = QHBoxLayout(self._trail)
        trail_row.setContentsMargins(0, 0, 0, 0)
        trail_row.setSpacing(4)
        self._trail_icon = QLabel()
        self._trail_icon.setFixedSize(14, 14)
        self._trail_text = QLabel()
        trail_row.addWidget(self._trail_icon)
        trail_row.addWidget(self._trail_text)
        self._trail.hide()
        self._kbd: Kbd | None = None

    def set_trailing(self, text: str = "", tone: str | None = None, icon_name: str | None = None) -> None:
        if not text:
            self._trail.hide()
            self._relayout()
            return
        color = tone_color(tone) if tone else P.TEXT_TERTIARY
        self._trail_text.setText(text)
        self._trail_text.setStyleSheet(f"color: {color}; font-size: 13px; font-weight: 500; background: transparent;")
        if icon_name:
            self._trail_icon.setPixmap(pixmap(icon_name, color, 14, 2.0))
            self._trail_icon.show()
        else:
            self._trail_icon.hide()
        self._trail.show()
        self._relayout()

    def set_key_hint(self, text: str) -> None:
        self._kbd = Kbd(text)
        self._kbd.setParent(self)
        self._kbd.setAttribute(Qt.WA_TransparentForMouseEvents)
        self._kbd.show()
        self._relayout()

    def _relayout(self) -> None:
        right = 10
        actions_w = 0
        for action in self.actions():
            if action.isVisible():
                actions_w += 28
        if self._trail.isVisible():
            self._trail.adjustSize()
            w = self._trail.sizeHint().width()
            self._trail.setGeometry(self.width() - w - right - actions_w, (self.height() - 18) // 2, w, 18)
            right += w + 6
        if self._kbd is not None:
            self._kbd.adjustSize()
            kw = self._kbd.sizeHint().width()
            self._kbd.move(self.width() - kw - 8 - actions_w, (self.height() - self._kbd.sizeHint().height()) // 2)
            right += kw + 12
        margins = self.textMargins()
        self.setTextMargins(margins.left(), 0, max(0, right - 10), 0)

    def resizeEvent(self, event):  # noqa: N802 - Qt API
        super().resizeEvent(event)
        self._relayout()


class SearchField(Field):
    """Search box with a leading magnifier and an optional key hint."""

    def __init__(self, placeholder: str, hint: str | None = None):
        super().__init__(placeholder=placeholder)
        self.addAction(icon("search", P.TEXT_TERTIARY, 16), QLineEdit.LeadingPosition)
        self.setClearButtonEnabled(False)
        if hint:
            self.set_key_hint(hint)


class PasswordField(Field):
    """Masked field with a show/hide toggle (and optional regenerate action)."""

    def __init__(self, placeholder: str = "", on_regenerate: Callable | None = None, mono: bool = True):
        super().__init__(placeholder=placeholder)
        if mono:
            self.setObjectName("secretField")
        self.setEchoMode(QLineEdit.Password)
        self._reveal = self.addAction(icon("eye", P.TEXT_SECONDARY, 16), QLineEdit.TrailingPosition)
        self._reveal.setToolTip("Mostrar")
        self._reveal.triggered.connect(self.toggle_visible)
        if on_regenerate is not None:
            regen = self.addAction(icon("sync", P.TEXT_SECONDARY, 16), QLineEdit.TrailingPosition)
            regen.setToolTip("Generar otra")
            regen.triggered.connect(lambda _=False: on_regenerate())
        # Never let the OS input method keep a copy of what is typed here.
        self.setAttribute(Qt.WA_InputMethodEnabled, False)
        self.setContextMenuPolicy(Qt.NoContextMenu)

    def toggle_visible(self) -> None:
        self.set_visible_text(self.echoMode() == QLineEdit.Password)

    def set_visible_text(self, visible: bool) -> None:
        self.setEchoMode(QLineEdit.Normal if visible else QLineEdit.Password)
        self._reveal.setIcon(icon("eye-off" if visible else "eye", P.TEXT_SECONDARY, 16))
        self._reveal.setToolTip("Ocultar" if visible else "Mostrar")

    def wipe(self) -> None:
        """Overwrite and clear (best effort: Qt keeps its own copies)."""
        self.setText("\0" * len(self.text()))
        self.clear()


def caps_lock_on() -> bool:
    """True when Caps Lock is active (Windows); False elsewhere or if unknown."""
    import sys
    if sys.platform != "win32":
        return False
    try:
        import ctypes
        return bool(ctypes.WinDLL("user32").GetKeyState(0x14) & 1)
    except Exception:
        return False


# ---- feedback -----------------------------------------------------------------
class StrengthMeter(QWidget):
    """Four segments + "✓ Muy fuerte · 131 bits" + an optional hint on the right."""

    LEVELS = {0: ("Muy débil", "danger"), 1: ("Débil", "danger"), 2: ("Aceptable", "warning"),
              3: ("Fuerte", "success"), 4: ("Muy fuerte", "success")}

    def __init__(self, show_hint: bool = True):
        super().__init__()
        col = QVBoxLayout(self)
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(6)
        bars = QHBoxLayout()
        bars.setSpacing(4)
        self._bars = []
        for _ in range(4):
            bar = QFrame()
            bar.setFixedHeight(4)
            bars.addWidget(bar)
            self._bars.append(bar)
        col.addLayout(bars)
        row = QHBoxLayout()
        row.setSpacing(6)
        self._icon = QLabel()
        self._icon.setFixedSize(13, 13)
        self._label = label("", "toneText")
        self._hint = label("", "tertiary")
        self._hint.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self._hint.setVisible(show_hint)
        row.addWidget(self._icon)
        row.addWidget(self._label)
        row.addSpacing(6)
        row.addWidget(self._hint, 1)
        col.addLayout(row)
        self.set_assessment(None)

    def set_assessment(self, assessment, hint: str = "") -> None:
        if assessment is None or not getattr(assessment, "length", 0):
            for bar in self._bars:
                bar.setStyleSheet(f"background: {P.SURFACE_3}; border-radius: 2px;")
            self._label.setText("")
            self._icon.clear()
            self._hint.setText(hint)
            return
        level = int(getattr(assessment, "level", 0))
        text, tone = self.LEVELS.get(level, ("", "danger"))
        color = tone_color(tone)
        filled = max(1, level)
        for i, bar in enumerate(self._bars):
            bar.setStyleSheet(f"background: {color if i < filled else P.SURFACE_3}; border-radius: 2px;")
        bits = int(round(getattr(assessment, "bits", 0)))
        self._label.setText(f"{text} · {bits} bits")
        set_prop(self._label, "tone", tone)
        self._icon.setPixmap(pixmap("check" if tone == "success" else "warning", color, 13, 2.0))
        self._hint.setText(hint)


class Banner(QFrame):
    """Alert box: icon, bold lead, text and optional actions on the right."""

    def __init__(self, tone: str = "info", title: str = "", text: str = "",
                 actions: Iterable[QWidget] = (), icon_name: str | None = None, compact: bool = False):
        super().__init__()
        self.setObjectName("banner")
        self.setProperty("tone", tone)
        row = QHBoxLayout(self)
        pad = 12 if compact else 16
        row.setContentsMargins(pad, pad - 2, pad, pad - 2)
        row.setSpacing(12)
        self._icon = icon_label(icon_name or TONE_ICON.get(tone, "info"), tone_color(tone), 18)
        row.addWidget(self._icon, 0, Qt.AlignTop)
        self._msg = QLabel()
        self._msg.setWordWrap(True)
        self._msg.setTextFormat(Qt.RichText)
        self._msg.setStyleSheet("background: transparent;")
        self._msg.setTextInteractionFlags(Qt.TextSelectableByMouse)
        row.addWidget(self._msg, 1)
        for widget in actions:
            row.addWidget(widget, 0, Qt.AlignVCenter)
        self.set_message(title, text, tone)

    def set_message(self, title: str, text: str, tone: str | None = None) -> None:
        from html import escape
        tone = tone or self.property("tone") or "info"
        if self.property("tone") != tone:
            self.setProperty("tone", tone)
            self._icon.setPixmap(pixmap(TONE_ICON.get(tone, "info"), tone_color(tone), 18))
            repolish(self)
        lead = f'<b style="color:{tone_color(tone)}">{escape(title)}</b> ' if title else ""
        body = escape(text).replace("\n", "<br>")
        self._msg.setText(f'<span style="color:{P.TEXT_PRIMARY}">{lead}{body}</span>')


def info_line(text: str, tone: str = "info", icon_name: str | None = None, wrap: bool = True) -> QWidget:
    """Small "ⓘ text" line used under fields and in footers."""
    w = QWidget()
    w.setObjectName("transparent")
    row = QHBoxLayout(w)
    row.setContentsMargins(0, 0, 0, 0)
    row.setSpacing(6)
    color = tone_color(tone)
    row.addWidget(icon_label(icon_name or TONE_ICON.get(tone, "info"), color, 14), 0, Qt.AlignTop)
    lbl = QLabel(text)
    lbl.setWordWrap(wrap)
    lbl.setStyleSheet(f"color: {color if tone in ('danger', 'warning', 'success', 'info') else P.TEXT_TERTIARY};"
                      " font-size: 13px; background: transparent;")
    row.addWidget(lbl, 1)
    w.text_label = lbl
    return w


class Spinner(QWidget):
    """Indeterminate 270° arc, used while a key is derived."""

    def __init__(self, size: int = 16, color: str | None = None):
        super().__init__()
        self.setFixedSize(size, size)
        self._angle = 0
        self._color = QColor(color or P.TEXT_PRIMARY)
        self._timer = QTimer(self)
        self._timer.setInterval(60)
        self._timer.timeout.connect(self._step)
        self._timer.start()

    def _step(self) -> None:
        self._angle = (self._angle + 30) % 360
        self.update()

    def stop(self) -> None:
        self._timer.stop()

    def paintEvent(self, _event):  # noqa: N802 - Qt API
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        pen = QPen(self._color, max(1.6, self.width() / 9))
        pen.setCapStyle(Qt.RoundCap)
        p.setPen(pen)
        m = pen.widthF()
        p.drawArc(QRectF(m, m, self.width() - 2 * m, self.height() - 2 * m), -self._angle * 16, 270 * 16)
        p.end()


class Ring(QWidget):
    """Progress ring with text in the middle (TOTP countdown, health score)."""

    def __init__(self, size: int = 36, width: float = 3.0, font_px: int = 12, caption: str = ""):
        super().__init__()
        self.setFixedSize(size, size)
        self._width = width
        self._fraction = 0.0
        self._text = ""
        self._caption = caption
        self._font_px = font_px
        self._color = QColor(P.ACCENT)

    def set_value(self, fraction: float, text: str, color: str | None = None) -> None:
        self._fraction = max(0.0, min(1.0, fraction))
        self._text = text
        if color:
            self._color = QColor(color)
        self.update()

    def paintEvent(self, _event):  # noqa: N802 - Qt API
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w = self._width
        rect = QRectF(w / 2 + 1, w / 2 + 1, self.width() - w - 2, self.height() - w - 2)
        p.setPen(QPen(QColor(P.SURFACE_3), w))
        p.drawEllipse(rect)
        pen = QPen(self._color, w)
        pen.setCapStyle(Qt.RoundCap)
        p.setPen(pen)
        p.drawArc(rect, 90 * 16, int(-self._fraction * 360 * 16))
        p.setPen(QColor(P.TEXT_PRIMARY))
        if self._caption:
            p.setFont(ui_font(self._font_px, 600))
            text_rect = QRectF(0, self.height() * 0.22, self.width(), self.height() * 0.42)
            p.drawText(text_rect, Qt.AlignHCenter | Qt.AlignBottom, self._text)
            p.setPen(QColor(P.TEXT_TERTIARY))
            p.setFont(ui_font(13))
            p.drawText(QRectF(0, self.height() * 0.62, self.width(), 20), Qt.AlignHCenter | Qt.AlignTop, self._caption)
        else:
            p.setFont(mono_font(self._font_px, 600))
            p.drawText(self.rect(), Qt.AlignCenter, self._text)
        p.end()


class StepList(QWidget):
    """Checklist of a long operation: done ✓, active spinner, pending ○, failed ✕."""

    def __init__(self, steps: Iterable[str], detail: dict | None = None):
        super().__init__()
        self._col = QVBoxLayout(self)
        self._col.setContentsMargins(0, 0, 0, 0)
        self._col.setSpacing(10)
        self._rows = []
        for i, text in enumerate(steps):
            row = QHBoxLayout()
            row.setSpacing(10)
            holder = QWidget()
            holder.setFixedSize(16, 16)
            holder_l = QHBoxLayout(holder)
            holder_l.setContentsMargins(0, 0, 0, 0)
            lbl = label(text, "body")
            side = label((detail or {}).get(i, ""), "monoSm")
            row.addWidget(holder)
            row.addWidget(lbl, 1)
            row.addWidget(side)
            self._col.addLayout(row)
            self._rows.append((holder, holder_l, lbl, side))
        self.set_state(-1)

    def set_detail(self, index: int, text: str) -> None:
        self._rows[index][3].setText(text)

    def set_state(self, active: int, failed: bool = False) -> None:
        """Steps before ``active`` are done; ``active`` spins (or fails)."""
        for i, (holder, holder_l, lbl, _side) in enumerate(self._rows):
            clear_layout(holder_l)
            if i < active:
                holder_l.addWidget(icon_label("check", P.SUCCESS, 16))
                lbl.setStyleSheet(f"color: {P.TEXT_PRIMARY}; background: transparent;")
            elif i == active and failed:
                holder_l.addWidget(icon_label("close", P.DANGER, 16))
                lbl.setStyleSheet(f"color: {P.DANGER}; background: transparent;")
            elif i == active:
                holder_l.addWidget(Spinner(16))
                lbl.setStyleSheet(f"color: {P.TEXT_PRIMARY}; font-weight: 500; background: transparent;")
            else:
                holder_l.addWidget(icon_label("circle", P.TEXT_TERTIARY, 16))
                lbl.setStyleSheet(f"color: {P.TEXT_TERTIARY}; background: transparent;")


def busy_bar() -> QProgressBar:
    bar = QProgressBar()
    bar.setRange(0, 0)
    bar.setTextVisible(False)
    return bar


class Card(QFrame):
    """Surface with an optional header row: icon, title, and a widget on the right."""

    def __init__(self, title: str = "", icon_name: str | None = None, right: QWidget | None = None,
                 name: str = "card", margins=(20, 16, 20, 18), spacing: int = 12, divider: bool = False):
        super().__init__()
        self.setObjectName(name)
        self.body = QVBoxLayout(self)
        self.body.setContentsMargins(*margins)
        self.body.setSpacing(spacing)
        if title or right is not None:
            head = QHBoxLayout()
            head.setSpacing(10)
            if icon_name:
                head.addWidget(icon_label(icon_name, P.TEXT_SECONDARY, 16))
            self.title_label = label(title, "titleSm")
            head.addWidget(self.title_label)
            head.addStretch(1)
            if right is not None:
                head.addWidget(right)
            self.body.addLayout(head)
            if divider:
                self.body.addWidget(hline())

    def add(self, item) -> None:
        _add(self.body, item)


class EmptyState(QWidget):
    """What happened, why, and the next action (board 11)."""

    def __init__(self, icon_name: str, title: str, text: str, actions: Iterable[QWidget] = (),
                 footnote: str = ""):
        super().__init__()
        self.setObjectName("transparent")
        col = QVBoxLayout(self)
        col.setContentsMargins(32, 24, 32, 24)
        col.setSpacing(10)
        col.addStretch(1)
        tile = IconTile(icon_name, size=96, icon_size=34, dashed=True, color=P.ACCENT)
        col.addWidget(tile, 0, Qt.AlignHCenter)
        col.addSpacing(10)
        self.title = label(title, "titleSm", align=Qt.AlignHCenter, wrap=True)
        col.addWidget(self.title)
        self.text = label(text, "secondary", align=Qt.AlignHCenter, wrap=True)
        self.text.setMaximumWidth(320)
        # Centred through stretches, not an alignment flag: an aligned item gets its
        # one-line size hint and a wrapped text would be cut after the first line.
        text_row = QHBoxLayout()
        text_row.setContentsMargins(0, 0, 0, 0)
        text_row.addStretch(1)
        text_row.addWidget(self.text, 100)
        text_row.addStretch(1)
        col.addLayout(text_row)
        col.addSpacing(8)
        for widget in actions:
            widget.setMinimumWidth(260)
            col.addWidget(widget, 0, Qt.AlignHCenter)
        if footnote:
            note = label(footnote, "tertiary", align=Qt.AlignHCenter, wrap=True)
            note.setMaximumWidth(320)
            note_row = QHBoxLayout()
            note_row.setContentsMargins(0, 0, 0, 0)
            note_row.addStretch(1)
            note_row.addWidget(note, 100)
            note_row.addStretch(1)
            col.addLayout(note_row)
        col.addStretch(2)


# ---- toasts -------------------------------------------------------------------
class Toast(QFrame):
    """Bottom-right notice, 360 px, optional countdown and one action."""

    closed = Signal()

    def __init__(self, parent: QWidget, title: str, text: str = "", tone: str | None = None,
                 icon_name: str = "check", action_text: str | None = None, on_action: Callable | None = None,
                 countdown: int = 0, on_timeout: Callable | None = None, timeout_ms: int = 5000):
        super().__init__(parent)
        self.setObjectName("toast")
        if tone:
            self.setProperty("tone", tone)
        self.setFixedWidth(360)
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(ELEVATION_2.blur * 2)
        shadow.setOffset(0, ELEVATION_2.y)
        shadow.setColor(QColor(ELEVATION_2.color(P)))
        self.setGraphicsEffect(shadow)
        col = QVBoxLayout(self)
        col.setContentsMargins(12, 12, 12, 10 if countdown else 12)
        col.setSpacing(8)
        row = QHBoxLayout()
        row.setSpacing(10)
        row.addWidget(IconTile(icon_name, tone=tone, size=30, icon_size=16,
                               color=tone_color(tone) if tone else P.TEXT_PRIMARY), 0, Qt.AlignTop)
        texts = QVBoxLayout()
        texts.setSpacing(1)
        texts.addWidget(label(title, "bodyStrong", wrap=True))
        self._sub = label(text, "tertiary", wrap=True)
        texts.addWidget(self._sub)
        row.addLayout(texts, 1)
        self._on_action = on_action
        if action_text:
            btn = Button(action_text, "secondary")
            btn.clicked.connect(self._act)
            row.addWidget(btn, 0, Qt.AlignVCenter)
        col.addLayout(row)
        self._countdown = countdown
        self._left = countdown
        self._text_template = text
        self._on_timeout = on_timeout
        self._bar = None
        if countdown:
            self._bar = QProgressBar()
            self._bar.setObjectName("thin")
            self._bar.setRange(0, countdown * 10)
            self._bar.setValue(countdown * 10)
            self._bar.setTextVisible(False)
            col.addWidget(self._bar)
            self._ticks = countdown * 10
            self._timer = QTimer(self)
            self._timer.setInterval(100)
            self._timer.timeout.connect(self._tick)
            self._timer.start()
            self._render_left()
        else:
            QTimer.singleShot(timeout_ms, self.dismiss)

    def _render_left(self) -> None:
        if "{s}" in self._text_template:
            self._sub.setText(self._text_template.replace("{s}", str(max(0, self._left))))

    def _tick(self) -> None:
        self._ticks -= 1
        self._bar.setValue(max(0, self._ticks))
        left = (self._ticks + 9) // 10
        if left != self._left:
            self._left = left
            self._render_left()
        if self._ticks <= 0:
            self._timer.stop()
            if self._on_timeout:
                self._on_timeout()
            self.dismiss()

    def _act(self) -> None:
        if self._on_action:
            self._on_action()
        self.dismiss()

    def dismiss(self) -> None:
        if self.isVisible() or self.parent() is not None:
            self.hide()
            self.closed.emit()
            self.deleteLater()


class ToastHost:
    """Stacks toasts in the bottom-right corner of a window."""

    def __init__(self, window: QWidget, margin: int = 20):
        self._window = window
        self._margin = margin
        self._toasts: list[Toast] = []
        window.installEventFilter(_ResizeWatcher(window, self.relayout))

    def show(self, title: str, text: str = "", **kwargs) -> Toast:
        key = kwargs.pop("key", None)
        if key:
            for t in list(self._toasts):
                if getattr(t, "_key", None) == key:
                    t.dismiss()
        toast = Toast(self._window, title, text, **kwargs)
        toast._key = key
        toast.closed.connect(lambda t=toast: self._forget(t))
        self._toasts.append(toast)
        toast.adjustSize()
        toast.show()
        toast.raise_()
        self.relayout()
        return toast

    def _forget(self, toast: Toast) -> None:
        if toast in self._toasts:
            self._toasts.remove(toast)
        self.relayout()

    def clear(self) -> None:
        for t in list(self._toasts):
            t.dismiss()

    def relayout(self) -> None:
        y = self._window.height() - self._margin
        for toast in reversed(self._toasts):
            toast.adjustSize()
            # The width is fixed (360 px): measure wrapped text at that width.
            h = toast.heightForWidth(toast.width()) if toast.hasHeightForWidth() else -1
            if h <= 0:
                h = toast.sizeHint().height()
            y -= h
            toast.setGeometry(self._window.width() - toast.width() - self._margin, y, toast.width(), h)
            y -= 10


class _ResizeWatcher(QWidget):
    def __init__(self, parent: QWidget, callback: Callable):
        super().__init__(parent)
        self.hide()
        self._callback = callback

    def eventFilter(self, obj, event):  # noqa: N802 - Qt API
        if event.type() == QEvent.Resize:
            self._callback()
        return False


# ---- dialogs ------------------------------------------------------------------
class Scrim(QWidget):
    """Veil painted over a window while one of its modal dialogs is open."""

    def __init__(self, parent: QWidget):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, False)
        self.setGeometry(parent.rect())
        self._watch = _ResizeWatcher(parent, lambda: self.setGeometry(parent.rect()))
        parent.installEventFilter(self._watch)

    def paintEvent(self, _event):  # noqa: N802 - Qt API
        p = QPainter(self)
        p.fillRect(self.rect(), QColor(P.SCRIM))
        p.end()


DIALOG_WIDTHS = {"s": 480, "m": 640, "l": 880, "xl": 1000}


class AvDialog(QDialog):
    """Secondary-dialog anatomy (board 20): header · optional status strip · body · footer.

    Frameless, with the ELEVATION_3 shadow, a scrim over the parent window and
    Esc to cancel. The primary button names the action; destructive actions use
    ``dangerSolid`` and open a separate confirmation.
    """

    def __init__(self, parent: QWidget | None, title: str, subtitle: str = "", icon_name: str | None = None,
                 width: str = "m", tone: str | None = None, avatar: str | None = None, scroll: bool = True,
                 closable: bool = True):
        super().__init__(parent)
        self.setObjectName("avDialog")
        self.setWindowTitle(title)
        self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setModal(True)
        self._scrim = None
        outer = QVBoxLayout(self)
        outer.setContentsMargins(28, 28, 28, 28)
        self.frame = QFrame()
        self.frame.setObjectName("dialogFrame")
        shadow = QGraphicsDropShadowEffect(self.frame)
        shadow.setBlurRadius(ELEVATION_3.blur * 2)
        shadow.setOffset(0, ELEVATION_3.y)
        shadow.setColor(QColor(ELEVATION_3.color(P)))
        self.frame.setGraphicsEffect(shadow)
        outer.addWidget(self.frame)
        self.frame.setFixedWidth(DIALOG_WIDTHS.get(width, 640) if isinstance(width, str) else int(width))

        col = QVBoxLayout(self.frame)
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(0)

        # header
        self.header = QFrame()
        self.header.setObjectName("dialogHeader")
        head = QHBoxLayout(self.header)
        head.setContentsMargins(24, 18, 16, 16)
        head.setSpacing(14)
        if avatar is not None:
            head.addWidget(Avatar(avatar, "md"), 0, Qt.AlignTop)
        elif icon_name:
            head.addWidget(IconTile(icon_name, tone=tone, size=36, icon_size=18), 0, Qt.AlignTop)
        titles = QVBoxLayout()
        titles.setSpacing(3)
        self.title_label = label(title, "title", wrap=True)
        titles.addWidget(self.title_label)
        self.subtitle_label = label(subtitle, "secondary", wrap=True)
        self.subtitle_label.setVisible(bool(subtitle))
        titles.addWidget(self.subtitle_label)
        head.addLayout(titles, 1)
        self.header_right = QHBoxLayout()
        self.header_right.setSpacing(8)
        head.addLayout(self.header_right)
        if closable:
            close = icon_button("close", "Cerrar (Esc)", self.reject, 16)
            head.addWidget(close, 0, Qt.AlignTop)
        col.addWidget(self.header)

        # optional status strip
        self.strip = QVBoxLayout()
        self.strip.setContentsMargins(24, 0, 24, 0)
        col.addLayout(self.strip)

        # body
        self.body_widget = QWidget()
        self.body_widget.setObjectName("dialogBody")
        self.body = QVBoxLayout(self.body_widget)
        self.body.setContentsMargins(24, 20, 24, 20)
        self.body.setSpacing(14)
        if scroll:
            area = QScrollArea()
            area.setObjectName("plain")
            area.setWidgetResizable(True)
            area.setFrameShape(QFrame.NoFrame)
            area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
            area.setWidget(self.body_widget)
            self._area = area
            col.addWidget(area, 1)
        else:
            self._area = None
            col.addWidget(self.body_widget, 1)

        # footer
        self.footer = QFrame()
        self.footer.setObjectName("dialogFooter")
        foot = QHBoxLayout(self.footer)
        foot.setContentsMargins(24, 14, 24, 14)
        foot.setSpacing(10)
        self.footer_note = label("", "tertiary", wrap=True)
        foot.addWidget(self.footer_note, 1)
        self.footer_buttons = QHBoxLayout()
        self.footer_buttons.setSpacing(10)
        foot.addLayout(self.footer_buttons)
        col.addWidget(self.footer)
        QShortcut(QKeySequence(Qt.Key_Escape), self, activated=self.reject)
        # Steps and tabs rebuild the body while the dialog is open: refit on the
        # next turn of the event loop, once Qt has shown the new widgets.
        self._refit_timer = QTimer(self)
        self._refit_timer.setSingleShot(True)
        self._refit_timer.setInterval(0)
        self._refit_timer.timeout.connect(self._fit)
        self.body_widget.installEventFilter(self)

    # building helpers
    def add_status(self, widget: QWidget) -> None:
        self.strip.setContentsMargins(24, 16, 24, 0)
        self.strip.addWidget(widget)

    def add(self, item) -> None:
        _add(self.body, item)

    def add_button(self, button: QWidget) -> QWidget:
        self.footer_buttons.addWidget(button)
        return button

    def set_note(self, text: str) -> None:
        self.footer_note.setText(text)

    # sizing and scrim
    def refit(self) -> None:
        """Resize to the current content (also done automatically when the body changes)."""
        self._refit_timer.start()

    def eventFilter(self, obj, event):  # noqa: N802 - Qt API
        if obj is self.body_widget and event.type() == QEvent.LayoutRequest and self.isVisible():
            self._refit_timer.start()
        return super().eventFilter(obj, event)

    @staticmethod
    def _height_at(widget: QWidget, width: int) -> int:
        # Wrapped text makes sizeHint() guess a width; ask for the real one.
        if widget.hasHeightForWidth():
            height = widget.heightForWidth(width)
            if height > 0:
                return height
        return widget.sizeHint().height()

    def _fit(self) -> None:
        parent = self.parentWidget()
        if self._area is not None:
            width = self.frame.maximumWidth()
            screen = (parent.window().geometry() if parent is not None else None)
            limit = int((screen.height() if screen else 900) * 0.9) - 56
            chrome = (self._height_at(self.header, width) + self._height_at(self.footer, width)
                      + self.strip.sizeHint().height() + 8)
            body_h = self._height_at(self.body_widget, width)
            self._area.setFixedHeight(min(body_h + 2, max(160, limit - chrome)))
            self.frame.updateGeometry()
            self.layout().invalidate()
        self.adjustSize()
        if parent is not None:
            top = parent.window()
            geo = top.frameGeometry() if top.isVisible() else top.geometry()
            self.move(geo.center() - QPoint(self.width() // 2, self.height() // 2))

    def showEvent(self, event):  # noqa: N802 - Qt API
        parent = self.parentWidget()
        if parent is not None and self._scrim is None and parent.window().isVisible():
            self._scrim = Scrim(parent.window())
            self._scrim.show()
            self._scrim.raise_()
        self._fit()
        super().showEvent(event)

    def done(self, result):  # noqa: D401 - Qt API
        if self._scrim is not None:
            self._scrim.hide()
            self._scrim.deleteLater()
            self._scrim = None
        super().done(result)


class ConfirmDialog(AvDialog):
    """Destructive confirmation (board 05): focus starts on Cancelar; Enter never confirms."""

    def __init__(self, parent, title: str, text: str, confirm_text: str, *, items: Iterable[str] = (),
                 type_word: str | None = None, icon_name: str = "trash", tone: str = "danger",
                 checkbox: str | None = None):
        super().__init__(parent, title, text, icon_name=icon_name, tone=tone, width="s", scroll=False)
        self.subtitle_label.setObjectName("secondary")
        items = list(items)
        if items:
            box = Card(name="cardSunken", margins=(14, 12, 14, 12), spacing=4)
            for item in items:
                box.add(label(item, "body"))
            self.add(box)
        self._check = None
        if checkbox:
            from PySide6.QtWidgets import QCheckBox
            self._check = QCheckBox(checkbox)
            self._check.toggled.connect(self._validate)
            self.add(self._check)
        self._word = type_word
        self._field = None
        if type_word:
            prompt = QLabel(f"Escribe <b style='font-family: monospace'>{type_word}</b> para confirmar")
            prompt.setObjectName("label")
            self.add(prompt)
            self._field = Field(mono=True)
            self._field.textChanged.connect(self._validate)
            self._field.setAttribute(Qt.WA_InputMethodEnabled, False)
            self.add(self._field)
        if not items and not type_word and not checkbox:
            self.body_widget.hide()
        self.cancel_btn = self.add_button(Button("Cancelar", "secondary", on_click=self.reject))
        self.confirm_btn = self.add_button(Button(confirm_text, "dangerSolid" if tone == "danger" else "primary",
                                                  on_click=self.accept))
        self.confirm_btn.setAutoDefault(False)
        self.cancel_btn.setDefault(True)
        self._validate()
        QTimer.singleShot(0, lambda: (self._field or self.cancel_btn).setFocus())

    def _validate(self, *_):
        ok = True
        if self._field is not None:
            ok = self._field.text().strip().upper() == self._word
        if self._check is not None:
            ok = ok and self._check.isChecked()
        self.confirm_btn.setEnabled(ok)

    def keyPressEvent(self, event):  # noqa: N802 - Qt API
        # Enter must not confirm a destructive action by accident.
        if event.key() in (Qt.Key_Return, Qt.Key_Enter):
            event.accept()
            return
        super().keyPressEvent(event)


def confirm(parent, title: str, text: str, confirm_text: str, **kwargs) -> bool:
    return ConfirmDialog(parent, title, text, confirm_text, **kwargs).exec() == QDialog.Accepted


def notify(parent, title: str, text: str, tone: str = "info", button: str = "Entendido") -> None:
    """Small informational dialog in the kit style (replaces QMessageBox)."""
    icon_name = TONE_ICON.get(tone, "info")
    dlg = AvDialog(parent, title, "", icon_name=icon_name, tone=tone, width="s", scroll=False)
    msg = label(text, "body", wrap=True, selectable=True)
    dlg.add(msg)
    dlg.add_button(Button(button, "primary", on_click=dlg.accept))
    dlg.exec()


def fit_width(widget: QWidget, minimum: int) -> None:
    widget.setMinimumWidth(minimum)
    widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)


class FlowLayout(QLayout):
    """Left-to-right layout that wraps to the next line (tag chips, share tiles)."""

    def __init__(self, parent: QWidget | None = None, spacing: int = 6):
        super().__init__(parent)
        self._items = []
        self._spacing = spacing
        self.setContentsMargins(0, 0, 0, 0)

    def addItem(self, item):  # noqa: N802 - Qt API
        self._items.append(item)

    def count(self) -> int:
        return len(self._items)

    def itemAt(self, index):  # noqa: N802 - Qt API
        return self._items[index] if 0 <= index < len(self._items) else None

    def takeAt(self, index):  # noqa: N802 - Qt API
        return self._items.pop(index) if 0 <= index < len(self._items) else None

    def expandingDirections(self):  # noqa: N802 - Qt API
        return Qt.Orientation(0)

    def hasHeightForWidth(self) -> bool:  # noqa: N802 - Qt API
        return True

    def heightForWidth(self, width: int) -> int:  # noqa: N802 - Qt API
        return self._arrange(QRect(0, 0, width, 0), apply=False)

    def setGeometry(self, rect):  # noqa: N802 - Qt API
        super().setGeometry(rect)
        self._arrange(rect, apply=True)

    def sizeHint(self) -> QSize:  # noqa: N802 - Qt API
        return self.minimumSize()

    def minimumSize(self) -> QSize:  # noqa: N802 - Qt API
        size = QSize()
        for item in self._items:
            size = size.expandedTo(item.minimumSize())
        m = self.contentsMargins()
        return size + QSize(m.left() + m.right(), m.top() + m.bottom())

    def _arrange(self, rect, apply: bool) -> int:
        m = self.contentsMargins()
        area = rect.adjusted(m.left(), m.top(), -m.right(), -m.bottom())
        x, y, line_h = area.x(), area.y(), 0
        for item in self._items:
            hint = item.sizeHint()
            if x + hint.width() > area.right() + 1 and line_h > 0:
                x = area.x()
                y += line_h + self._spacing
                line_h = 0
            if apply:
                item.setGeometry(QRect(QPoint(x, y), hint))
            x += hint.width() + self._spacing
            line_h = max(line_h, hint.height())
        return y + line_h - rect.y() + m.bottom()
