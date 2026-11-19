"""Design tokens for the AegisVault desktop UI: direction "Tinta y marfil".

Source of truth is the "Tokens" board of the redesign canvas. Colours live in
two ``Palette`` instances (``DARK`` is the default, ``LIGHT`` the light mode) so
the stylesheet can be built once per mode; type, spacing, radii, elevation and
dimensions do not depend on the mode.

Colour is reserved for meaning: ivory ``ACCENT`` marks the primary action and
the selection, and the status colours are the only saturated hues. Never let a
colour carry meaning alone: pair it with an icon or a word.

Qt notes:

* QSS has no ``outline`` and no ``:focus-visible``. Draw ``FOCUS_RING`` as a
  ``FOCUS_RING_W`` px border and remove 1 px of padding, driven by a dynamic
  property (``focusRing="true"``) that an event filter sets on Tab focus.
* Colours with alpha: ``QColor`` takes ``#AARRGGBB`` (``qcolor_hex``), QSS takes
  ``rgba(r, g, b, a)`` with ``a`` in 0-255 (``qss_rgba``).
* Font sizes are pixels: use ``font-size: Npx`` / ``QFont.setPixelSize``, not pt.
  QSS ignores ``line-height`` and ``text-transform``; they are kept here for
  layout maths and for upper-casing overline text in code.
* At most one ``QGraphicsDropShadowEffect`` per widget (see ``Shadow``).
"""
from __future__ import annotations

from dataclasses import dataclass, fields

# Colour ---------------------------------------------------------------------


@dataclass(frozen=True)
class Palette:
    """Every colour token for one mode. Field names are the token names."""

    MODE: str  # "dark" | "light"

    # Background and surfaces
    BG_BASE: str  # window; entry-list panel
    SURFACE_1: str  # top bar, sidebar, detail panel
    SURFACE_2: str  # cards, fields, dialogs
    SURFACE_3: str  # selected, pressed, menus, tooltip
    SCRIM: str  # modal veil, already "#AARRGGBB" for QColor

    # Borders
    BORDER_SUBTLE: str  # separators, rows (decorative)
    BORDER_DEFAULT: str  # panels and cards (decorative)
    BORDER_CONTROL: str  # fields, toggles, checkboxes: >= 3:1 on every surface

    # Text
    TEXT_PRIMARY: str
    TEXT_SECONDARY: str  # labels, metadata
    TEXT_TERTIARY: str  # hints, timestamps
    TEXT_DISABLED: str  # disabled controls only (exempt from contrast)

    # Accent, selection, focus
    ACCENT: str  # primary button, link, progress
    ACCENT_HOVER: str
    ACCENT_PRESSED: str
    ON_ACCENT: str  # text and icons on ACCENT
    SELECTION_BORDER: str  # border of the selected list row
    FOCUS_RING: str  # keyboard focus, FOCUS_RING_W px

    # States: text/icon colour, badge or banner background, its border
    SUCCESS: str
    SUCCESS_BG: str
    SUCCESS_BORDER: str
    WARNING: str
    WARNING_BG: str
    WARNING_BORDER: str
    DANGER: str
    DANGER_BG: str
    DANGER_BORDER: str
    DANGER_SOLID: str  # destructive button fill
    ON_DANGER_SOLID: str  # text on DANGER_SOLID
    INFO: str
    INFO_BG: str
    INFO_BORDER: str

    def colors(self) -> dict[str, str]:
        """Colour tokens by name (``MODE`` excluded)."""
        return {f.name: getattr(self, f.name) for f in fields(self) if f.name != "MODE"}

    @property
    def is_dark(self) -> bool:
        return self.MODE == "dark"


DARK = Palette(
    MODE="dark",
    BG_BASE="#0B0E14",
    SURFACE_1="#12161F",
    SURFACE_2="#1A1F2A",
    SURFACE_3="#232937",
    SCRIM="#B805070B",
    BORDER_SUBTLE="#1F2430",
    BORDER_DEFAULT="#2C3342",
    BORDER_CONTROL="#6C7486",
    TEXT_PRIMARY="#ECE8DF",
    TEXT_SECONDARY="#B1B7C3",
    TEXT_TERTIARY="#8A92A2",
    TEXT_DISABLED="#5A6172",
    ACCENT="#EADFC8",
    ACCENT_HOVER="#F4ECDB",
    ACCENT_PRESSED="#D6C9AE",
    ON_ACCENT="#141720",
    SELECTION_BORDER="#7A766C",
    FOCUS_RING="#7FB2FF",
    SUCCESS="#5CC98A",
    SUCCESS_BG="#13271C",
    SUCCESS_BORDER="#235A3B",
    WARNING="#E9B44C",
    WARNING_BG="#2B2213",
    WARNING_BORDER="#5E4A1F",
    DANGER="#F07A6E",
    DANGER_BG="#2F1718",
    DANGER_BORDER="#6E302C",
    DANGER_SOLID="#B8433A",
    ON_DANGER_SOLID="#FFF5F2",
    INFO="#7FB2FF",
    INFO_BG="#142035",
    INFO_BORDER="#2D4A75",
)

LIGHT = Palette(
    MODE="light",
    BG_BASE="#F3F0E8",
    SURFACE_1="#F9F7F2",
    SURFACE_2="#FFFFFF",
    SURFACE_3="#ECE8DF",
    SCRIM="#66161A22",
    BORDER_SUBTLE="#E6E1D6",
    BORDER_DEFAULT="#D5CFC2",
    BORDER_CONTROL="#7E838D",
    TEXT_PRIMARY="#161A22",
    TEXT_SECONDARY="#434A58",
    TEXT_TERTIARY="#5B6270",
    TEXT_DISABLED="#A3A7B0",
    ACCENT="#1B2130",
    ACCENT_HOVER="#2A3142",
    ACCENT_PRESSED="#0F131C",
    ON_ACCENT="#F4ECDB",
    SELECTION_BORDER="#7D796F",
    FOCUS_RING="#2F6FE0",
    SUCCESS="#1D7645",
    SUCCESS_BG="#E3F1E8",
    SUCCESS_BORDER="#A9D2B8",
    WARNING="#8F5A00",
    WARNING_BG="#FBF0DA",
    WARNING_BORDER="#E3C27E",
    DANGER="#B3362C",
    DANGER_BG="#FBE6E3",
    DANGER_BORDER="#E7AFA8",
    DANGER_SOLID="#B3362C",
    ON_DANGER_SOLID="#FFF5F2",
    INFO="#2459C2",
    INFO_BG="#E3ECFB",
    INFO_BORDER="#A9C2EE",
)

PALETTES: dict[str, Palette] = {"dark": DARK, "light": LIGHT}


def palette(mode: str = "dark") -> Palette:
    """Return the palette for ``mode`` ("dark" or "light")."""
    try:
        return PALETTES[mode]
    except KeyError:
        raise ValueError(f"unknown colour mode: {mode!r}") from None


def _rgb(hex6: str) -> tuple[int, int, int]:
    value = hex6.lstrip("#")
    if len(value) != 6:
        raise ValueError(f"expected #RRGGBB, got {hex6!r}")
    return int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16)


def _alpha_byte(alpha: float) -> int:
    if not 0.0 <= alpha <= 1.0:
        raise ValueError(f"alpha must be within 0..1, got {alpha}")
    return round(alpha * 255)


def qss_rgba(hex6: str, alpha: float) -> str:
    """``"#RRGGBB"`` plus 0..1 alpha -> ``"rgba(r, g, b, a)"`` for QSS (a in 0..255)."""
    r, g, b = _rgb(hex6)
    return f"rgba({r}, {g}, {b}, {_alpha_byte(alpha)})"


def qcolor_hex(hex6: str, alpha: float) -> str:
    """``"#RRGGBB"`` plus 0..1 alpha -> ``"#AARRGGBB"`` for ``QColor``."""
    r, g, b = _rgb(hex6)
    return f"#{_alpha_byte(alpha):02X}{r:02X}{g:02X}{b:02X}"


# Typography -------------------------------------------------------------------

FONT_UI = "Inter"
FONT_MONO = "JetBrains Mono"
FONT_UI_STACK = '"Inter", "Segoe UI Variable", "Segoe UI", Arial, sans-serif'
FONT_MONO_STACK = '"JetBrains Mono", "Cascadia Code", Consolas, monospace'


@dataclass(frozen=True)
class TypeStyle:
    size: int  # px
    line_height: int  # px; layout maths only, QSS ignores it
    weight: int
    letter_spacing: float = 0.0  # em
    mono: bool = False
    uppercase: bool = False  # upper-case the text in code; QSS has no text-transform

    def qss(self) -> str:
        """Font declarations for a QSS rule body."""
        family = FONT_MONO_STACK if self.mono else FONT_UI_STACK
        parts = [f"font-family: {family};", f"font-size: {self.size}px;", f"font-weight: {self.weight};"]
        if self.letter_spacing:
            parts.append(f"letter-spacing: {self.letter_spacing * self.size:.2f}px;")
        return " ".join(parts)


TYPE_DISPLAY = TypeStyle(30, 38, 600, letter_spacing=-0.01)
TYPE_TITLE_LG = TypeStyle(22, 30, 600)
TYPE_TITLE_MD = TypeStyle(17, 24, 600)
TYPE_TITLE_SM = TypeStyle(15, 22, 600)
TYPE_BODY = TypeStyle(14, 20, 400)
TYPE_BODY_STRONG = TypeStyle(14, 20, 500)
TYPE_LABEL = TypeStyle(13, 18, 500)
TYPE_CAPTION = TypeStyle(12, 16, 400)
TYPE_OVERLINE = TypeStyle(11, 16, 600, letter_spacing=0.06, uppercase=True)
TYPE_MONO_SECRET = TypeStyle(15, 22, 500, letter_spacing=0.02, mono=True)  # revealed secrets
TYPE_MONO_CODE = TypeStyle(26, 32, 600, letter_spacing=0.06, mono=True)  # live TOTP code
TYPE_MONO_SM = TypeStyle(12, 16, 400, mono=True)  # hashes, paths, counters

# Spacing (4 px base) ----------------------------------------------------------

SPACE_1 = 4
SPACE_2 = 8
SPACE_3 = 12
SPACE_4 = 16
SPACE_5 = 20
SPACE_6 = 24
SPACE_8 = 32
SPACE_10 = 40
SPACE_12 = 48
SPACE_16 = 64

# Radii ------------------------------------------------------------------------

RADIUS_XS = 4  # badges, checkboxes
RADIUS_SM = 6  # buttons, fields, square chips
RADIUS_MD = 8  # cards, menus, toasts
RADIUS_LG = 12  # dialogs, large panels
RADIUS_FULL = 999  # toggles, tag chips: in QSS use pill_radius(height) instead


def pill_radius(height: int) -> int:
    """Qt does not clamp an oversized border-radius, so pills use half the height."""
    return height // 2


# Elevation --------------------------------------------------------------------
# ELEVATION_0: flat, border only (panels). ELEVATION_1: surface + border, no
# shadow (cards). Only levels 2 and 3 cast a shadow.


@dataclass(frozen=True)
class Shadow:
    blur: int
    y: int
    alpha_dark: float
    alpha_light: float

    def color(self, pal: Palette) -> str:
        """Shadow colour for ``pal`` as ``#AARRGGBB``, ready for QColor."""
        return qcolor_hex("#000000", self.alpha_dark if pal.is_dark else self.alpha_light)


ELEVATION_2 = Shadow(blur=12, y=4, alpha_dark=0.40, alpha_light=0.12)  # menus, toasts
ELEVATION_3 = Shadow(blur=32, y=12, alpha_dark=0.55, alpha_light=0.18)  # dialogs

# Dimensions -------------------------------------------------------------------

MIN_TARGET = 32  # smallest click target
CONTROL_H_SM = 32
CONTROL_H_MD = 36
CONTROL_H_LG = 44
ICON_SM = 16
ICON_MD = 20
FOCUS_RING_W = 2
TOPBAR_H = 56
SIDEBAR_W = 232
SIDEBAR_W_COMPACT = 64  # icon rail with the health ring
LIST_W_MIN = 360
LIST_W_MAX = 420
LIST_W_COMPACT = 340
ENTRY_ROW_H = 60
# Below this window width use the compact layout: icon-only top-bar actions
# (except "Bloquear ahora"), SIDEBAR_W_COMPACT, LIST_W_COMPACT, history folded.
COMPACT_BELOW_W = 1400

# Motion and security timing ---------------------------------------------------
# Clipboard clearing and auto-lock defaults belong to VaultSettings
# (clipboard_clear_seconds, auto_lock_seconds), not here.

DURATION_FAST_MS = 120  # colour and opacity transitions only
SECRET_REVEAL_S = 15  # a revealed secret hides itself again
LOCK_WARN_S = 60  # the lock indicator switches to WARNING from here down
