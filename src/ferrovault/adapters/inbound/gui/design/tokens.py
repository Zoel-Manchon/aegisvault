"""Shared visual tokens for the AegisVault PySide component system.

The GUI intentionally uses a small design-token layer so Qt Widgets can feel
like a coherent product rather than many one-off forms.  Keep visual constants
here and consume them from components/theme.py.
"""
from __future__ import annotations

# Core palette --------------------------------------------------------------
# Dark enterprise slate with restrained indigo/cyan signal colors.
ACCENT = "#5B6CFF"
ACCENT_2 = "#22D3EE"
ACCENT_DIM = "#172554"
BG = "#050712"
PANEL = "#0A1020"
PANEL_2 = "#0F172A"
ELEV = "#141F33"
ELEV_2 = "#1B2740"
BORDER = "#263654"
BORDER_SOFT = "#1B2742"
TEXT = "#F8FAFC"
MUTED = "#94A3B8"
MUTED_2 = "#64748B"
DANGER = "#FB7185"
GOOD = "#34D399"
WARNING = "#FBBF24"

# Layout scale --------------------------------------------------------------
SPACE_1 = 4
SPACE_2 = 8
SPACE_3 = 12
SPACE_4 = 16
SPACE_5 = 20
SPACE_6 = 24
SPACE_8 = 32
RADIUS_SM = 10
RADIUS_MD = 14
RADIUS_LG = 18
RADIUS_XL = 24

# Component dimensions ------------------------------------------------------
TOPBAR_HEIGHT = 68
SIDEBAR_WIDTH = 196
LIST_MIN_WIDTH = 360
LIST_MAX_WIDTH = 470
ENTRY_CARD_HEIGHT = 72
