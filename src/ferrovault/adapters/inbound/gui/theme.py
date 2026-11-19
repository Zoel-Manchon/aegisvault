"""AegisVault desktop theme, "Tinta y marfil", built from design/tokens.py.

``build_stylesheet(palette)`` turns one Palette into the application QSS.
The active palette is chosen once at start-up from ``AEGISVAULT_THEME``
("dark", the default, or "light") and exposed as ``PALETTE`` so widgets that
tint icons or paint pixmaps use the same colours as the stylesheet.

Keyboard focus: QSS has no ``:focus-visible``, so ``focus_ring.FocusRingFilter``
sets ``focusRing="true"`` on a widget that received focus from the keyboard;
the ``[focusRing="true"]`` rules below draw it as a 2 px border and take 1 px
off the padding so the content does not move.
"""
from __future__ import annotations

import hashlib
import os
import sys
from pathlib import Path

from .design.tokens import (
    CONTROL_H_MD,
    FONT_MONO_STACK,
    FOCUS_RING_W,
    RADIUS_LG,
    RADIUS_MD,
    RADIUS_SM,
    RADIUS_XS,
    TYPE_BODY,
    TYPE_CAPTION,
    TYPE_LABEL,
    TYPE_MONO_CODE,
    TYPE_MONO_SECRET,
    TYPE_OVERLINE,
    TYPE_TITLE_LG,
    TYPE_TITLE_MD,
    TYPE_TITLE_SM,
    TYPE_DISPLAY,
    TYPE_BODY_STRONG,
    TYPE_MONO_SM,
    Palette,
    palette,
    qss_rgba,
)


def _mode_from_env() -> str:
    mode = os.environ.get("AEGISVAULT_THEME", "dark").strip().lower()
    return mode if mode in {"dark", "light"} else "dark"


def build_stylesheet(p: Palette) -> str:
    """Application stylesheet for one palette."""
    ring = f"{FOCUS_RING_W}px solid {p.FOCUS_RING}"
    # A control is CONTROL_H_MD tall: 1 px border + 7 px padding around a
    # 20 px content box. With the 2 px focus ring the padding drops to 6 px.
    control_min = CONTROL_H_MD - 2 * (1 + 7)
    return f"""
/* Family and base size (14 px) come from the application font, set in
   typography.load_fonts(). A global font rule here would override every
   setFont() call: mono_font(15) would come out as 14 px. */
QWidget {{
    background: {p.BG_BASE};
    color: {p.TEXT_PRIMARY};
}}
QLabel {{ background: transparent; }}
QWidget#detailContent, QWidget#featureGrid, QWidget#settingsPage {{ background: transparent; }}

/* Shell: flush columns divided by hairlines, no floating cards ------------- */
QWidget#appShell {{ background: {p.BG_BASE}; }}
QFrame#topbar {{
    background: {p.SURFACE_1};
    border: none;
    border-bottom: 1px solid {p.BORDER_SUBTLE};
    border-radius: 0;
}}
QFrame#sidebar {{
    background: {p.SURFACE_1};
    border: none;
    border-right: 1px solid {p.BORDER_SUBTLE};
    border-radius: 0;
}}
QFrame#listWrap {{
    background: {p.BG_BASE};
    border: none;
    border-right: 1px solid {p.BORDER_SUBTLE};
    border-radius: 0;
}}
QFrame#detailPanel {{
    background: {p.SURFACE_1};
    border: none;
    border-radius: 0;
}}
QScrollArea#detailScroll, QScrollArea#settingsScroll {{ background: transparent; border: none; }}
QFrame#sectionHeader {{ background: transparent; border: none; }}
QFrame#lineSeparator {{ background: {p.BORDER_SUBTLE}; max-height: 1px; border: none; }}

/* Typography ----------------------------------------------------------------- */
QLabel#brand {{ font-size: {TYPE_TITLE_SM.size}px; font-weight: 600; color: {p.TEXT_PRIMARY}; }}
QLabel#brandAccent {{ font-size: {TYPE_TITLE_SM.size}px; font-weight: 600; color: {p.ACCENT}; }}
QLabel#tagline {{ color: {p.TEXT_TERTIARY}; font-size: 10px; font-weight: 600; letter-spacing: 0.6px; }}
QLabel#h1 {{ font-size: {TYPE_TITLE_LG.size}px; font-weight: 600; color: {p.TEXT_PRIMARY}; }}
QLabel#h2 {{ font-size: {TYPE_TITLE_SM.size}px; font-weight: 600; color: {p.TEXT_PRIMARY}; }}
QLabel#muted {{ color: {p.TEXT_SECONDARY}; font-size: {TYPE_LABEL.size}px; }}
QLabel#smallMuted {{ color: {p.TEXT_TERTIARY}; font-size: {TYPE_CAPTION.size}px; }}
QLabel#tinyMuted {{ color: {p.TEXT_TERTIARY}; font-size: {TYPE_OVERLINE.size}px; }}
QLabel#mono {{
    font-family: {FONT_MONO_STACK};
    color: {p.TEXT_TERTIARY};
    font-size: {TYPE_OVERLINE.size}px;
    font-weight: 600;
    letter-spacing: 0.6px;
}}
QLabel#metricValue {{ color: {p.TEXT_PRIMARY}; font-size: {TYPE_TITLE_LG.size}px; font-weight: 600; }}
QLabel#secret {{ {TYPE_MONO_SECRET.qss()} color: {p.TEXT_PRIMARY}; }}
QLabel#code {{ {TYPE_MONO_CODE.qss()} color: {p.TEXT_PRIMARY}; }}

/* Cards ---------------------------------------------------------------------- */
QFrame#featureCard, QFrame#emptyCard, QFrame#detailCard, QFrame#healthCard,
QFrame#metricCard, QFrame#metricTile, QFrame#panel {{
    background: {p.SURFACE_2};
    border: 1px solid {p.BORDER_DEFAULT};
    border-radius: {RADIUS_MD}px;
}}
QFrame#emptyCard {{ background: {p.SURFACE_1}; }}
QFrame#metricTile:hover, QFrame#metricCard:hover {{ border: 1px solid {p.BORDER_CONTROL}; }}

/* Entry rows: transparent until hovered; the selected row adds a border, so
   selection never relies on colour alone. */
QFrame#entryCard {{
    background: transparent;
    border: 1px solid transparent;
    border-radius: {RADIUS_MD}px;
}}
QFrame#entryCard:hover {{ background: {p.SURFACE_2}; }}
QFrame#entryCard[selected="true"] {{
    background: {p.SURFACE_3};
    border: 1px solid {p.SELECTION_BORDER};
}}

/* Badges ------------------------------------------------------------------------ */
QLabel#badgeOn, QLabel#badgeOff, QLabel#badgeSoft, QLabel#ztPill {{
    border-radius: 11px;
    padding: 3px 10px;
    font-weight: 600;
    font-size: {TYPE_CAPTION.size}px;
}}
QLabel#badgeOn {{ background: {p.SUCCESS_BG}; color: {p.SUCCESS}; border: 1px solid {p.SUCCESS_BORDER}; }}
QLabel#badgeSoft {{ background: {p.INFO_BG}; color: {p.INFO}; border: 1px solid {p.INFO_BORDER}; }}
QLabel#badgeOff {{ background: {p.SURFACE_2}; color: {p.TEXT_SECONDARY}; border: 1px solid {p.BORDER_DEFAULT}; }}
QLabel#ztPill {{ background: {p.SURFACE_2}; color: {p.TEXT_SECONDARY}; border: 1px solid {p.BORDER_DEFAULT}; }}
QLabel#ztPill[tone="good"] {{ background: {p.SUCCESS_BG}; color: {p.SUCCESS}; border: 1px solid {p.SUCCESS_BORDER}; }}
QLabel#ztPill[tone="warn"] {{ background: {p.WARNING_BG}; color: {p.WARNING}; border: 1px solid {p.WARNING_BORDER}; }}
QLabel#ztPill[tone="danger"] {{ background: {p.DANGER_BG}; color: {p.DANGER}; border: 1px solid {p.DANGER_BORDER}; }}

/* Inputs ------------------------------------------------------------------------ */
QLineEdit, QComboBox, QSpinBox, QPlainTextEdit, QTextEdit {{
    background: {p.BG_BASE};
    border: 1px solid {p.BORDER_CONTROL};
    border-radius: {RADIUS_SM}px;
    padding: 7px 10px;
    color: {p.TEXT_PRIMARY};
    selection-background-color: {p.ACCENT};
    selection-color: {p.ON_ACCENT};
}}
QLineEdit, QComboBox, QSpinBox {{ min-height: {control_min}px; }}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QPlainTextEdit:focus, QTextEdit:focus {{
    border: 1px solid {p.FOCUS_RING};
}}
QLineEdit[focusRing="true"], QComboBox[focusRing="true"], QSpinBox[focusRing="true"],
QPlainTextEdit[focusRing="true"], QTextEdit[focusRing="true"] {{
    border: {ring};
    padding: 6px 9px;
}}
QLineEdit:disabled, QComboBox:disabled, QSpinBox:disabled, QPlainTextEdit:disabled, QTextEdit:disabled {{
    color: {p.TEXT_DISABLED};
    background: {p.SURFACE_1};
    border: 1px solid {p.BORDER_DEFAULT};
}}
QLineEdit[error="true"] {{ border: 1px solid {p.DANGER}; }}
QComboBox::drop-down {{ border: none; width: 24px; }}
/* The editor inside a spin box is a QLineEdit too: without this it inherits the
   control padding and the number is clipped away. */
QAbstractSpinBox QLineEdit {{ background: transparent; border: none; padding: 0; min-height: 0; }}
QComboBox QAbstractItemView {{
    background: {p.SURFACE_2};
    border: 1px solid {p.BORDER_DEFAULT};
    border-radius: {RADIUS_MD}px;
    selection-background-color: {p.SURFACE_3};
    selection-color: {p.TEXT_PRIMARY};
    outline: none;
    padding: 4px;
}}
QCheckBox, QRadioButton {{ spacing: 10px; padding: 4px; color: {p.TEXT_PRIMARY}; background: transparent; }}
QCheckBox::indicator, QRadioButton::indicator {{
    width: 16px;
    height: 16px;
    border: 1px solid {p.BORDER_CONTROL};
    background: {p.BG_BASE};
}}
QCheckBox::indicator {{ border-radius: {RADIUS_XS}px; }}
QRadioButton::indicator {{ border-radius: 9px; }}
QCheckBox::indicator:checked, QRadioButton::indicator:checked {{
    background: {p.ACCENT};
    border: 1px solid {p.ACCENT};
}}
QCheckBox[focusRing="true"]::indicator, QRadioButton[focusRing="true"]::indicator {{ border: {ring}; }}
QCheckBox:disabled, QRadioButton:disabled {{ color: {p.TEXT_DISABLED}; }}

/* Buttons ----------------------------------------------------------------------- */
QPushButton {{
    background: {p.SURFACE_2};
    border: 1px solid {p.BORDER_DEFAULT};
    border-radius: {RADIUS_SM}px;
    padding: 7px 14px;
    min-height: {control_min}px;
    color: {p.TEXT_PRIMARY};
    font-size: {TYPE_LABEL.size}px;
    font-weight: 500;
    outline: none;
}}
QPushButton:hover {{ background: {p.SURFACE_3}; border: 1px solid {p.BORDER_CONTROL}; }}
QPushButton:pressed {{ background: {p.BORDER_DEFAULT}; }}
QPushButton:disabled {{ color: {p.TEXT_DISABLED}; background: {p.SURFACE_1}; border: 1px solid {p.BORDER_SUBTLE}; }}
QPushButton[focusRing="true"] {{ border: {ring}; padding: 6px 13px; }}

QPushButton#primary {{
    background: {p.ACCENT};
    color: {p.ON_ACCENT};
    border: 1px solid {p.ACCENT};
    font-weight: 600;
}}
QPushButton#primary:hover {{ background: {p.ACCENT_HOVER}; border: 1px solid {p.ACCENT_HOVER}; }}
QPushButton#primary:pressed {{ background: {p.ACCENT_PRESSED}; border: 1px solid {p.ACCENT_PRESSED}; }}
QPushButton#primary:disabled {{ background: {p.SURFACE_3}; color: {p.TEXT_DISABLED}; border: 1px solid {p.SURFACE_3}; }}
QPushButton#primary[focusRing="true"] {{ border: {ring}; }}

QPushButton#ghost, QPushButton#topNav {{ background: transparent; border: 1px solid transparent; }}
QPushButton#ghost:hover, QPushButton#topNav:hover {{ background: {p.SURFACE_3}; border: 1px solid transparent; }}
QPushButton#ghost:pressed, QPushButton#topNav:pressed {{ background: {p.BORDER_DEFAULT}; }}
QPushButton#ghost[focusRing="true"], QPushButton#topNav[focusRing="true"] {{ border: {ring}; }}
QPushButton#topNav {{ padding: 7px 8px; }}
QPushButton#topNav[focusRing="true"] {{ padding: 6px 7px; }}
QPushButton#topNav::menu-indicator {{ image: none; width: 0px; }}

/* Destructive: outlined in DANGER; the solid DANGER_SOLID fill is kept for the
   final confirmation inside a dialog. */
QPushButton#danger {{ background: transparent; color: {p.DANGER}; border: 1px solid {p.DANGER_BORDER}; }}
QPushButton#danger:hover {{ background: {p.DANGER_BG}; border: 1px solid {p.DANGER}; }}
QPushButton#danger:pressed {{ background: {p.DANGER_BORDER}; }}
QPushButton#danger[focusRing="true"] {{ border: {ring}; }}
QPushButton#dangerSolid {{ background: {p.DANGER_SOLID}; color: {p.ON_DANGER_SOLID}; border: 1px solid {p.DANGER_SOLID}; font-weight: 600; }}
QPushButton#dangerSolid[focusRing="true"] {{ border: {ring}; }}
/* An id selector outranks QPushButton:disabled, so each kind says it explicitly:
   a disabled destructive button must not look ready to click. */
QPushButton#danger:disabled {{ background: transparent; color: {p.TEXT_DISABLED}; border: 1px solid {p.BORDER_SUBTLE}; }}
QPushButton#dangerSolid:disabled {{ background: {p.SURFACE_3}; color: {p.TEXT_DISABLED}; border: 1px solid {p.SURFACE_3}; }}
QPushButton#ghost:disabled {{ background: transparent; color: {p.TEXT_DISABLED}; border: 1px solid transparent; }}

QPushButton#filterBtn, QPushButton#pageBtn {{ background: {p.SURFACE_2}; border: 1px solid {p.BORDER_DEFAULT}; }}
QPushButton#pageBtn, QPushButton#pageActive {{ min-width: 18px; padding: 7px 7px; }}
QPushButton#topNavActive, QPushButton#pageActive {{
    background: {p.SURFACE_3};
    border: 1px solid {p.SELECTION_BORDER};
    font-weight: 600;
}}

/* Sidebar: the active item gets a bar, weight and a lighter fill. */
QPushButton#sideNav, QPushButton#sideActive {{
    text-align: left;
    padding: 7px 10px 7px 8px;
    border: none;
    border-left: 3px solid transparent;
    border-radius: {RADIUS_SM}px;
    font-size: {TYPE_BODY.size}px;
}}
QPushButton#sideNav {{ background: transparent; color: {p.TEXT_SECONDARY}; font-weight: 400; }}
QPushButton#sideNav:hover {{ background: {p.SURFACE_2}; color: {p.TEXT_PRIMARY}; }}
QPushButton#sideActive {{
    background: {p.SURFACE_3};
    color: {p.TEXT_PRIMARY};
    font-weight: 600;
    border-left: 3px solid {p.ACCENT};
}}
QPushButton#sideNav[focusRing="true"], QPushButton#sideActive[focusRing="true"] {{
    border: {ring};
    border-left: 3px solid {p.FOCUS_RING};
    padding: 5px 8px 5px 8px;
}}

QPushButton#categoryCard, QPushButton#ztActionCard {{
    text-align: left;
    padding: 14px 16px;
    border-radius: {RADIUS_MD}px;
    background: {p.SURFACE_2};
    border: 1px solid {p.BORDER_DEFAULT};
    color: {p.TEXT_PRIMARY};
    font-size: {TYPE_LABEL.size}px;
    font-weight: 500;
}}
QPushButton#categoryCard:hover, QPushButton#ztActionCard:hover {{
    background: {p.SURFACE_3};
    border: 1px solid {p.BORDER_CONTROL};
}}
QPushButton#categoryCard[focusRing="true"], QPushButton#ztActionCard[focusRing="true"] {{
    border: {ring};
    padding: 13px 15px;
}}

/* Lists and tables ---------------------------------------------------------------- */
QListWidget {{ background: transparent; border: none; outline: none; }}
QListWidget::item {{ border: none; margin: 0; padding: 0; }}
QListWidget::item:selected {{ background: transparent; }}
QListWidget[focusRing="true"] {{ border: {ring}; border-radius: {RADIUS_MD}px; }}
QTableWidget, QTableView, QTreeView {{
    background: {p.SURFACE_2};
    alternate-background-color: {p.SURFACE_1};
    border: 1px solid {p.BORDER_DEFAULT};
    border-radius: {RADIUS_MD}px;
    gridline-color: {p.BORDER_SUBTLE};
    selection-background-color: {p.SURFACE_3};
    selection-color: {p.TEXT_PRIMARY};
    outline: none;
}}
QTableWidget[focusRing="true"], QTableView[focusRing="true"], QTreeView[focusRing="true"] {{ border: {ring}; }}
QHeaderView::section {{
    background: {p.SURFACE_1};
    color: {p.TEXT_TERTIARY};
    border: none;
    border-bottom: 1px solid {p.BORDER_DEFAULT};
    padding: 8px;
    font-size: {TYPE_CAPTION.size}px;
    font-weight: 600;
}}

/* Progress, scroll bars, menus, tooltips ----------------------------------------- */
QProgressBar {{
    background: {p.SURFACE_3};
    border: none;
    border-radius: 3px;
    max-height: 6px;
    min-height: 6px;
    color: transparent;
}}
QProgressBar::chunk {{ background: {p.ACCENT}; border-radius: 3px; }}
QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px; }}
QScrollBar::handle:vertical {{ background: {p.BORDER_DEFAULT}; border-radius: 3px; min-height: 32px; }}
QScrollBar:horizontal {{ background: transparent; height: 10px; margin: 2px; }}
QScrollBar::handle:horizontal {{ background: {p.BORDER_DEFAULT}; border-radius: 3px; min-width: 32px; }}
QScrollBar::handle:hover {{ background: {p.BORDER_CONTROL}; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; width: 0; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}
QSplitter::handle {{ background: {p.BORDER_SUBTLE}; }}
QMenu {{
    background: {p.SURFACE_2};
    border: 1px solid {p.BORDER_DEFAULT};
    border-radius: {RADIUS_MD}px;
    padding: 4px;
}}
QMenu::item {{ padding: 8px 24px 8px 12px; border-radius: {RADIUS_SM}px; color: {p.TEXT_PRIMARY}; margin: 1px 0; }}
QMenu::item:selected {{ background: {p.SURFACE_3}; }}
QMenu::item:disabled {{ color: {p.TEXT_DISABLED}; }}
QMenu::separator {{ height: 1px; background: {p.BORDER_SUBTLE}; margin: 4px 8px; }}
QToolTip {{
    background: {p.TEXT_PRIMARY};
    color: {p.BG_BASE};
    border: none;
    border-radius: {RADIUS_SM}px;
    padding: 6px 8px;
    font-size: {TYPE_CAPTION.size}px;
}}

/* Dialogs ------------------------------------------------------------------------- */
QDialog {{ background: {p.SURFACE_1}; }}
QFrame#dialogHero {{
    background: {p.SURFACE_2};
    border: 1px solid {p.BORDER_DEFAULT};
    border-radius: {RADIUS_LG}px;
}}
QFrame#settingsRow, QFrame#formCard {{
    background: {p.SURFACE_2};
    border: 1px solid {p.BORDER_DEFAULT};
    border-radius: {RADIUS_MD}px;
}}
QFrame#policyCallout {{
    background: {p.INFO_BG};
    border: 1px solid {p.INFO_BORDER};
    border-radius: {RADIUS_MD}px;
}}
QTabWidget#settingsTabs::pane {{
    background: {p.SURFACE_1};
    border: 1px solid {p.BORDER_DEFAULT};
    border-radius: {RADIUS_MD}px;
    top: -1px;
}}
QTabBar::tab {{
    background: transparent;
    border: none;
    border-bottom: 2px solid transparent;
    color: {p.TEXT_SECONDARY};
    padding: 8px 14px;
    margin-right: 4px;
    font-weight: 500;
}}
QTabBar::tab:hover {{ color: {p.TEXT_PRIMARY}; background: {p.SURFACE_2}; }}
QTabBar::tab:selected {{ color: {p.TEXT_PRIMARY}; border-bottom: 2px solid {p.ACCENT}; font-weight: 600; }}
QTabBar[focusRing="true"]::tab:selected {{ border: {ring}; }}

QDialog#startupSplash {{
    background: {p.SURFACE_1};
    border: 1px solid {p.BORDER_DEFAULT};
    border-radius: {RADIUS_LG}px;
}}
QLabel#splashTitle {{ color: {p.TEXT_PRIMARY}; font-size: {TYPE_DISPLAY.size}px; font-weight: 600; }}
QLabel#iconTile[hero="true"] {{ border-radius: 20px; }}
QLabel#splashStatus, QLabel#unlockStatus {{ color: {p.TEXT_SECONDARY}; font-size: {TYPE_CAPTION.size}px; font-weight: 500; }}
QProgressBar#splashProgress, QProgressBar#unlockProgress {{ background: {p.SURFACE_3}; border: none; border-radius: 3px; }}

/* Zero Trust command centre --------------------------------------------------------- */
QFrame#ztHero {{
    background: {p.SURFACE_2};
    border: 1px solid {p.BORDER_DEFAULT};
    border-radius: {RADIUS_LG}px;
}}
QFrame#ztScoreCard {{
    background: {p.SURFACE_1};
    border: 1px solid {p.BORDER_DEFAULT};
    border-radius: {RADIUS_MD}px;
}}
QFrame#ztTrustStrip {{
    background: {p.SURFACE_1};
    border: 1px solid {p.BORDER_SUBTLE};
    border-radius: {RADIUS_MD}px;
}}
QLabel#ztTitle {{ font-size: {TYPE_TITLE_LG.size}px; font-weight: 600; color: {p.TEXT_PRIMARY}; }}
QLabel#ztScore {{ font-family: {FONT_MONO_STACK}; font-size: 32px; font-weight: 600; color: {p.TEXT_PRIMARY}; }}
QFrame#ztSignalCard, QFrame#ztSummaryCard, QFrame#ztEvidence {{
    background: {p.SURFACE_2};
    border: 1px solid {p.BORDER_DEFAULT};
    border-radius: {RADIUS_MD}px;
}}
QFrame#ztSignalCard[tone="good"] {{ border: 1px solid {p.SUCCESS_BORDER}; }}
QFrame#ztSignalCard[tone="warn"] {{ border: 1px solid {p.WARNING_BORDER}; }}
QFrame#ztSignalCard[tone="danger"] {{ border: 1px solid {p.DANGER_BORDER}; }}
QFrame#ztEvidence {{ background: {p.SURFACE_1}; }}

/* Command palette ---------------------------------------------------------------------- */
QDialog#commandPalette {{ background: {p.SURFACE_2}; }}
QLineEdit#commandSearch {{
    min-height: 26px;
    padding: 7px 14px;
    border-radius: {RADIUS_MD}px;
    font-size: {TYPE_TITLE_MD.size - 1}px;
    background: {p.BG_BASE};
}}
QLineEdit#commandSearch[focusRing="true"] {{ padding: 6px 13px; }}
QListWidget#commandResults {{ background: transparent; border: none; padding: 4px 0; }}
QListWidget#commandResults::item {{
    min-height: 40px;
    padding: 4px 10px;
    margin: 1px 0;
    border-radius: {RADIUS_SM}px;
}}
QListWidget#commandResults::item:hover {{ background: {p.SURFACE_3}; }}
QListWidget#commandResults::item:selected {{
    background: {p.SURFACE_3};
    color: {p.TEXT_PRIMARY};
    border-left: 3px solid {p.ACCENT};
}}
""" + _kit_rules(p)


def _kit_rules(p: Palette) -> str:
    """Rules for the redesign component kit (components/kit.py and the screens)."""
    ring = f"{FOCUS_RING_W}px solid {p.FOCUS_RING}"
    tones = {
        "success": (p.SUCCESS, p.SUCCESS_BG, p.SUCCESS_BORDER),
        "warning": (p.WARNING, p.WARNING_BG, p.WARNING_BORDER),
        "danger": (p.DANGER, p.DANGER_BG, p.DANGER_BORDER),
        "info": (p.INFO, p.INFO_BG, p.INFO_BORDER),
    }
    tone_rules = []
    for tone, (fg, bg, border) in tones.items():
        tone_rules.append(f"""
QFrame#badge[tone="{tone}"], QFrame#lockPill[tone="{tone}"] {{ background: {bg}; border: 1px solid {border}; }}
QFrame#badge[tone="{tone}"] QLabel, QFrame#lockPill[tone="{tone}"] QLabel {{ color: {fg}; }}
QFrame#banner[tone="{tone}"] {{ background: {bg}; border: 1px solid {border}; }}
QLabel#bannerTitle[tone="{tone}"], QLabel#toneText[tone="{tone}"] {{ color: {fg}; }}
QFrame#statCard[tone="{tone}"] {{ border: 1px solid {border}; }}
QLabel#statTitle[tone="{tone}"] {{ color: {fg}; }}
QFrame#toast[tone="{tone}"] {{ border: 1px solid {border}; }}
QLabel#iconTile[tone="{tone}"] {{ background: {bg}; border: 1px solid {border}; }}
QPushButton#bannerAction[tone="{tone}"] {{ border: 1px solid {border}; }}
QFrame#chip[tone="{tone}"] {{ background: {bg}; border: 1px solid {border}; }}
QFrame#chip[tone="{tone}"] QLabel {{ color: {fg}; }}""")
    return f"""
/* ==== Redesign kit ================================================================ */
QLabel#display {{ font-size: {TYPE_DISPLAY.size}px; font-weight: 600; color: {p.TEXT_PRIMARY}; }}
QLabel#titleLg {{ font-size: {TYPE_TITLE_LG.size}px; font-weight: 600; color: {p.TEXT_PRIMARY}; }}
QLabel#title {{ font-size: {TYPE_TITLE_MD.size}px; font-weight: 600; color: {p.TEXT_PRIMARY}; }}
QLabel#titleSm {{ font-size: {TYPE_TITLE_SM.size}px; font-weight: 600; color: {p.TEXT_PRIMARY}; }}
QLabel#body {{ font-size: {TYPE_BODY.size}px; color: {p.TEXT_PRIMARY}; }}
QLabel#bodyStrong {{ font-size: {TYPE_BODY_STRONG.size}px; font-weight: 500; color: {p.TEXT_PRIMARY}; }}
QLabel#label {{ font-size: {TYPE_LABEL.size}px; font-weight: 500; color: {p.TEXT_PRIMARY}; }}
QLabel#secondary {{ font-size: {TYPE_LABEL.size}px; color: {p.TEXT_SECONDARY}; }}
QLabel#tertiary {{ font-size: {TYPE_CAPTION.size}px; color: {p.TEXT_TERTIARY}; }}
QLabel#overline {{ font-size: {TYPE_OVERLINE.size}px; font-weight: 600; color: {p.TEXT_TERTIARY}; }}
QLabel#monoSm {{ {TYPE_MONO_SM.qss()} color: {p.TEXT_SECONDARY}; }}
QLabel#monoBody {{ font-family: {FONT_MONO_STACK}; font-size: 14px; color: {p.TEXT_PRIMARY}; }}
QLabel#toneText {{ font-size: {TYPE_LABEL.size}px; font-weight: 600; }}
QLabel#kbd {{
    font-family: {FONT_MONO_STACK};
    font-size: 11px;
    color: {p.TEXT_SECONDARY};
    background: transparent;
    border: 1px solid {p.BORDER_DEFAULT};
    border-radius: {RADIUS_XS}px;
    padding: 1px 5px;
}}
QLabel#kbd[onAccent="true"] {{
    color: {p.ON_ACCENT};
    background: {qss_rgba(p.ON_ACCENT, 0.08)};
    border: 1px solid {qss_rgba(p.ON_ACCENT, 0.25)};
}}
QLabel#avatar {{
    background: {p.SURFACE_3};
    color: {p.TEXT_PRIMARY};
    border: 1px solid {p.BORDER_DEFAULT};
    border-radius: {RADIUS_SM}px;
    font-size: 15px;
    font-weight: 600;
}}
QLabel#avatar[size="lg"] {{ border-radius: {RADIUS_MD}px; font-size: 24px; }}
QLabel#avatar[size="sm"] {{ border-radius: {RADIUS_XS}px; font-size: 12px; }}
QLabel#avatar[muted="true"] {{ color: {p.TEXT_DISABLED}; background: {p.SURFACE_2}; }}
QLabel#iconTile {{
    background: {p.SURFACE_2};
    border: 1px solid {p.BORDER_DEFAULT};
    border-radius: {RADIUS_MD}px;
}}
QLabel#iconTile[dashed="true"] {{ border: 1px dashed {p.BORDER_CONTROL}; background: transparent; }}
QLabel#tag {{
    background: {p.SURFACE_3};
    color: {p.TEXT_PRIMARY};
    border-radius: 12px;
    padding: 3px 10px;
    font-size: {TYPE_LABEL.size}px;
}}
QFrame#hairline {{ background: {p.BORDER_SUBTLE}; border: none; min-height: 1px; max-height: 1px; }}
QFrame#vline {{ background: {p.BORDER_SUBTLE}; border: none; min-width: 1px; max-width: 1px; }}

/* Badges and pills: icon + word, never colour alone */
QFrame#badge {{ background: transparent; border: 1px solid {p.BORDER_DEFAULT}; border-radius: {RADIUS_XS}px; }}
QFrame#badge QLabel {{ background: transparent; color: {p.TEXT_SECONDARY}; font-size: {TYPE_CAPTION.size}px; font-weight: 600; }}
QFrame#badge[tone="neutral"] {{ background: {p.SURFACE_2}; }}
QFrame#badge[tone="mono"] QLabel {{ font-family: {FONT_MONO_STACK}; font-size: 11px; font-weight: 500; }}
QFrame#badge[tone="dashed"] {{ border: 1px dashed {p.BORDER_CONTROL}; }}
QFrame#lockPill {{ border-radius: 16px; background: transparent; border: 1px solid {p.BORDER_DEFAULT}; }}
QFrame#lockPill QLabel {{ background: transparent; font-size: {TYPE_LABEL.size}px; font-weight: 500; }}
QLabel#lockTime {{ font-family: {FONT_MONO_STACK}; font-size: {TYPE_LABEL.size}px; }}
QFrame#chip {{ background: {p.SURFACE_2}; border: 1px solid {p.BORDER_DEFAULT}; border-radius: 12px; }}
QFrame#chip QLabel {{ background: transparent; color: {p.TEXT_PRIMARY}; font-size: {TYPE_LABEL.size}px; }}
{"".join(tone_rules)}

/* Buttons */
QPushButton#primary[size="lg"], QPushButton[size="lg"] {{ min-height: 28px; font-size: {TYPE_TITLE_SM.size}px; }}
QPushButton#iconBtn {{
    background: transparent;
    border: 1px solid transparent;
    border-radius: {RADIUS_SM}px;
    padding: 6px;
    min-height: 18px;
    min-width: 18px;
}}
QPushButton#iconBtn:hover {{ background: {p.SURFACE_3}; }}
QPushButton#iconBtn:checked {{ background: {p.SURFACE_3}; }}
QPushButton#iconBtn[focusRing="true"] {{ border: {ring}; padding: 5px; }}
QPushButton#link {{
    background: transparent;
    border: none;
    padding: 0;
    min-height: 0;
    color: {p.TEXT_PRIMARY};
    text-decoration: underline;
    font-weight: 500;
    text-align: left;
}}
QPushButton#link:hover {{ color: {p.ACCENT_HOVER}; background: transparent; border: none; }}
QPushButton#link:disabled {{ color: {p.TEXT_DISABLED}; background: transparent; border: none; }}
QPushButton#link[focusRing="true"] {{ border: {ring}; padding: 0 2px; }}
QPushButton#bannerAction {{ background: transparent; border: 1px solid {p.BORDER_CONTROL}; }}
QPushButton#bannerAction:hover {{ background: {qss_rgba(p.TEXT_PRIMARY, 0.06)}; }}
QPushButton#bannerAction[focusRing="true"] {{ border: {ring}; }}
QPushButton#dropdown {{
    background: transparent;
    border: 1px solid {p.BORDER_CONTROL};
    text-align: left;
    padding: 7px 10px;
}}
QPushButton#dropdown::menu-indicator {{ image: none; width: 0px; }}
QPushButton#ghost::menu-indicator {{ image: none; width: 0px; }}
QPushButton#dropdown:hover {{ background: {p.SURFACE_2}; }}
QPushButton#dropdown[focusRing="true"] {{ border: {ring}; padding: 6px 9px; }}
QPushButton#searchTrigger {{
    background: {p.BG_BASE};
    border: 1px solid {p.BORDER_DEFAULT};
    color: {p.TEXT_TERTIARY};
    text-align: left;
    padding: 7px 10px;
    font-weight: 400;
}}
QPushButton#searchTrigger:hover {{ border: 1px solid {p.BORDER_CONTROL}; background: {p.BG_BASE}; }}
QPushButton#searchTrigger[focusRing="true"] {{ border: {ring}; padding: 6px 9px; }}
QPushButton#vaultSwitch {{
    background: transparent;
    border: 1px solid transparent;
    color: {p.TEXT_SECONDARY};
    padding: 4px 6px 4px 8px;
    min-height: 22px;
    font-weight: 400;
}}
QPushButton#vaultSwitch::menu-indicator {{ image: none; width: 0px; }}
QPushButton#vaultSwitch:hover {{ background: {p.SURFACE_2}; }}

/* Segmented control */
QFrame#segmented {{ background: {p.BG_BASE}; border: 1px solid {p.BORDER_DEFAULT}; border-radius: {RADIUS_MD}px; }}
QPushButton#segment {{
    background: transparent;
    border: 1px solid transparent;
    border-radius: {RADIUS_SM}px;
    color: {p.TEXT_SECONDARY};
    padding: 5px 12px;
    min-height: 20px;
    font-weight: 500;
}}
QPushButton#segment:hover {{ color: {p.TEXT_PRIMARY}; background: {p.SURFACE_2}; }}
QPushButton#segment:checked {{ background: {p.SURFACE_3}; color: {p.TEXT_PRIMARY}; font-weight: 600; border: 1px solid {p.BORDER_DEFAULT}; }}
QFrame#segmented[accent="true"] QPushButton#segment:checked {{
    background: {p.ACCENT};
    color: {p.ON_ACCENT};
    border: 1px solid {p.ACCENT};
}}
QPushButton#segment[focusRing="true"] {{ border: {ring}; }}
QPushButton#segment:disabled {{ color: {p.TEXT_DISABLED}; }}

/* Inputs */
QLineEdit[error="true"], QPlainTextEdit[error="true"] {{ border: 2px solid {p.DANGER}; padding: 6px 9px; }}
QLineEdit[ok="true"] {{ border: 1px solid {p.SUCCESS_BORDER}; }}
QLineEdit#mono, QPlainTextEdit#mono {{ font-family: {FONT_MONO_STACK}; font-size: 14px; }}
QLineEdit#secretField {{ font-family: {FONT_MONO_STACK}; font-size: 15px; }}
QLineEdit#bare {{ background: transparent; border: none; padding: 4px 2px; }}
QLineEdit#bare[focusRing="true"] {{ border: none; }}
QSlider::groove:horizontal {{ height: 4px; background: {p.SURFACE_3}; border-radius: 2px; }}
QSlider::sub-page:horizontal {{ background: {p.ACCENT}; border-radius: 2px; }}
QSlider::handle:horizontal {{
    background: {p.ACCENT};
    border: 2px solid {p.SURFACE_1};
    width: 14px;
    height: 14px;
    margin: -7px 0;
    border-radius: 9px;
}}
QSlider[focusRing="true"]::handle:horizontal {{ border: {ring}; }}

/* Surfaces */
QFrame#card {{ background: {p.SURFACE_2}; border: 1px solid {p.BORDER_DEFAULT}; border-radius: {RADIUS_MD}px; }}
QFrame#cardSunken {{ background: {p.SURFACE_1}; border: 1px solid {p.BORDER_DEFAULT}; border-radius: {RADIUS_MD}px; }}
QFrame#cardDashed {{ background: transparent; border: 1px dashed {p.BORDER_DEFAULT}; border-radius: {RADIUS_MD}px; }}
QFrame#cardSelected {{ background: {p.SURFACE_2}; border: 1px solid {p.ACCENT}; border-radius: {RADIUS_MD}px; }}
QFrame#banner {{ background: {p.SURFACE_2}; border: 1px solid {p.BORDER_DEFAULT}; border-radius: {RADIUS_MD}px; }}
QLabel#bannerTitle {{ font-weight: 600; }}
QFrame#toast {{ background: {p.SURFACE_2}; border: 1px solid {p.BORDER_DEFAULT}; border-radius: {RADIUS_MD}px; }}
QProgressBar#thin {{ max-height: 3px; min-height: 3px; border-radius: 1px; background: {p.SURFACE_3}; }}
QProgressBar#thin::chunk {{ background: {p.ACCENT}; border-radius: 1px; }}
QProgressBar[tone="success"]::chunk {{ background: {p.SUCCESS}; }}
QProgressBar[tone="warning"]::chunk {{ background: {p.WARNING}; }}
QProgressBar[tone="danger"]::chunk {{ background: {p.DANGER}; }}
QScrollArea#plain {{ background: transparent; border: none; }}
QWidget#transparent {{ background: transparent; }}

/* Window shell */
QFrame#pageHeader {{ background: {p.BG_BASE}; border: none; border-bottom: 1px solid {p.BORDER_SUBTLE}; }}
QFrame#brandPanel {{ background: {p.SURFACE_1}; border: none; border-right: 1px solid {p.BORDER_SUBTLE}; }}
QWidget#unlockForm, QWidget#page {{ background: {p.BG_BASE}; }}
QPushButton#navItem {{
    background: transparent;
    border: 1px solid transparent;
    border-radius: {RADIUS_SM}px;
    text-align: left;
    padding: 0;
    min-height: 34px;
}}
QPushButton#navItem:hover {{ background: {p.SURFACE_2}; }}
QPushButton#navItem[active="true"] {{ background: {p.SURFACE_3}; }}
QPushButton#navItem[focusRing="true"] {{ border: {ring}; }}
QPushButton#navItem QLabel {{ background: transparent; }}
QLabel#navText {{ color: {p.TEXT_SECONDARY}; font-size: {TYPE_BODY.size}px; }}
QLabel#navText[active="true"] {{ color: {p.TEXT_PRIMARY}; font-weight: 600; }}
QLabel#navCount {{ color: {p.TEXT_TERTIARY}; font-size: {TYPE_CAPTION.size}px; font-family: {FONT_MONO_STACK}; }}
QPushButton#settingsNavItem {{
    background: transparent;
    border: none;
    border-left: 3px solid transparent;
    border-radius: {RADIUS_SM}px;
    text-align: left;
    padding: 7px 10px;
    color: {p.TEXT_SECONDARY};
    font-weight: 400;
}}
QPushButton#settingsNavItem:hover {{ background: {p.SURFACE_2}; color: {p.TEXT_PRIMARY}; }}
QPushButton#settingsNavItem[active="true"] {{
    background: {p.SURFACE_3};
    color: {p.TEXT_PRIMARY};
    border-left: 3px solid {p.ACCENT};
    font-weight: 600;
}}
QPushButton#settingsNavItem[focusRing="true"] {{ border: {ring}; }}

/* Entry rows */
QFrame#entryCard[deleted="true"] {{ border: 1px dashed {p.BORDER_DEFAULT}; }}
QLabel#rowTitle {{ font-size: {TYPE_BODY.size}px; font-weight: 500; color: {p.TEXT_PRIMARY}; }}
QLabel#rowSub {{ font-size: {TYPE_LABEL.size}px; color: {p.TEXT_SECONDARY}; }}
QLabel#rowTitle[muted="true"], QLabel#rowSub[muted="true"] {{ color: {p.TEXT_TERTIARY}; }}

/* Detail */
QLabel#fieldLabel {{ color: {p.TEXT_SECONDARY}; font-size: {TYPE_BODY.size}px; }}
QLabel#fieldValue {{ color: {p.TEXT_PRIMARY}; font-size: {TYPE_TITLE_SM.size}px; }}
QLabel#statValue {{ font-size: {TYPE_DISPLAY.size}px; font-weight: 600; color: {p.TEXT_PRIMARY}; }}
QLabel#statTitle {{ font-size: {TYPE_LABEL.size}px; font-weight: 600; color: {p.TEXT_SECONDARY}; }}
QFrame#statCard {{ background: {p.SURFACE_1}; border: 1px solid {p.BORDER_DEFAULT}; border-radius: {RADIUS_MD}px; }}

/* Audit timeline */
QFrame#blockRow {{ background: {p.SURFACE_1}; border: 1px solid {p.BORDER_DEFAULT}; border-radius: {RADIUS_MD}px; }}
QFrame#blockRow:hover {{ border: 1px solid {p.BORDER_CONTROL}; }}
QFrame#blockRow[selected="true"] {{ border: 1px solid {p.SELECTION_BORDER}; background: {p.SURFACE_2}; }}
QFrame#blockRow[state="broken"] {{ border: 2px solid {p.DANGER}; background: {p.DANGER_BG}; }}

/* Dialog chrome (frameless, drawn by AvDialog) */
QFrame#dialogFrame {{ background: {p.SURFACE_1}; border: 1px solid {p.BORDER_DEFAULT}; border-radius: {RADIUS_LG}px; }}
QFrame#dialogHeader {{ background: transparent; border: none; border-bottom: 1px solid {p.BORDER_SUBTLE}; }}
QFrame#dialogFooter {{ background: transparent; border: none; border-top: 1px solid {p.BORDER_SUBTLE}; }}
QWidget#dialogBody {{ background: transparent; }}
QDialog#avDialog {{ background: transparent; }}

/* Editor, tables and pages */
QFrame#editorAside {{ background: transparent; border: none; border-left: 1px solid {p.BORDER_SUBTLE}; }}
QFrame#tagInput {{
    background: {p.BG_BASE};
    border: 1px solid {p.BORDER_CONTROL};
    border-radius: {RADIUS_SM}px;
}}
QFrame#tableHead {{ background: transparent; border: none; border-bottom: 1px solid {p.BORDER_SUBTLE}; }}
QFrame#tableRow {{ background: transparent; border: none; border-bottom: 1px solid {p.BORDER_SUBTLE}; }}
QFrame#tableRow:hover {{ background: {p.SURFACE_2}; }}
QFrame#tableRow[tone="danger"] {{ background: {p.DANGER_BG}; }}
QFrame#issueRow {{ background: transparent; border: none; border-top: 1px solid {p.BORDER_SUBTLE}; }}
QFrame#shareTile {{ background: {p.BG_BASE}; border: 1px solid {p.BORDER_DEFAULT}; border-radius: {RADIUS_SM}px; }}
QFrame#shareTile[state="saved"] {{ border: 1px solid {p.SUCCESS_BORDER}; }}
QFrame#shareTile[state="active"] {{ border: 2px solid {p.ACCENT}; }}
QLabel#fpTile {{ background: {p.BG_BASE}; border: 1px solid {p.BORDER_DEFAULT}; border-radius: {RADIUS_SM}px; color: {p.TEXT_PRIMARY}; }}
QFrame#revokePanel {{ background: {p.SURFACE_2}; border: 1px solid {p.DANGER_BORDER}; border-radius: {RADIUS_MD}px; }}
QFrame#tabBar {{ background: transparent; border: none; border-bottom: 1px solid {p.BORDER_SUBTLE}; }}
QPushButton#tabBtn {{ background: transparent; border: none; border-bottom: 2px solid transparent; border-radius: 0; padding: 8px 12px; color: {p.TEXT_SECONDARY}; font-weight: 500; min-height: 0; }}
QPushButton#tabBtn:hover {{ color: {p.TEXT_PRIMARY}; background: transparent; }}
QPushButton#tabBtn[active="true"] {{ color: {p.TEXT_PRIMARY}; border-bottom: 2px solid {p.ACCENT}; font-weight: 600; }}
QFrame#splashCard {{ background: {p.SURFACE_1}; border: 1px solid {p.BORDER_DEFAULT}; border-radius: {RADIUS_LG}px; }}

/* Command palette */
QFrame#paletteFrame {{ background: {p.SURFACE_1}; border: 1px solid {p.BORDER_DEFAULT}; border-radius: {RADIUS_LG}px; }}
QFrame#paletteHead {{ background: transparent; border: none; border-bottom: 1px solid {p.BORDER_SUBTLE}; }}
QFrame#paletteFoot {{ background: transparent; border: none; border-top: 1px solid {p.BORDER_SUBTLE}; }}
QFrame#paletteRow {{ background: transparent; border: none; border-radius: {RADIUS_SM}px; }}
QFrame#paletteRow[active="true"] {{ background: {p.SURFACE_3}; }}
QLabel#dangerNote {{ color: {p.DANGER}; font-size: 11px; font-weight: 600; background: transparent; }}
QLineEdit#paletteSearch {{ background: transparent; border: none; font-size: 16px; padding: 4px 2px; }}
QLineEdit#paletteSearch[focusRing="true"] {{ border: none; }}
QListWidget#paletteList::item {{ border-radius: {RADIUS_SM}px; padding: 0; margin: 0; }}
QListWidget#paletteList::item:selected {{ background: {p.SURFACE_3}; }}
QListWidget#paletteList::item:hover {{ background: {p.SURFACE_2}; }}
"""


PALETTE: Palette = palette(_mode_from_env())
STYLESHEET: str = build_stylesheet(PALETTE)


_CHECK_SVG = ('<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 16 16">'
              '<path d="M3.6 8.4l2.9 2.9 5.9-6.6" fill="none" stroke="{color}" stroke-width="2" '
              'stroke-linecap="round" stroke-linejoin="round"/></svg>')


def _ui_cache_dir() -> Path:
    if sys.platform == "win32":
        base = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
        return Path(base) / "AegisVault" / "ui"
    base = os.environ.get("XDG_CACHE_HOME")
    return (Path(base) if base else Path.home() / ".cache") / "aegisvault" / "ui"


_DOT_SVG = ('<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 16 16">'
            '<circle cx="8" cy="8" r="3.5" fill="{color}"/></svg>')
_CHEVRON_SVG = ('<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24">'
                '<path d="M6 9l6 6 6-6" fill="none" stroke="{color}" stroke-width="2" '
                'stroke-linecap="round" stroke-linejoin="round"/></svg>')


def _cached_svg(name: str, svg: str) -> str | None:
    """Write ``svg`` once to the per-user UI cache; returns its path for ``url()``."""
    target = _ui_cache_dir() / f"{name}-{hashlib.sha256(svg.encode()).hexdigest()[:16]}.svg"
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.is_file() or target.read_text(encoding="utf-8") != svg:
            target.write_text(svg, encoding="utf-8")
    except OSError:
        return None
    return target.as_posix()


def indicator_qss(p: Palette) -> str:
    """Rules that draw the tick of checked boxes and the arrow of combo boxes.

    Qt style sheets only load these images from files, so each SVG (just a
    path in a palette colour) is written once to the per-user cache. If that
    fails the box stays filled (still reads as on) and the combo has no arrow.
    """
    rules = []
    check = _cached_svg("check", _CHECK_SVG.format(color=p.ON_ACCENT))
    if check:
        rules.append(f'QCheckBox::indicator:checked {{ image: url("{check}"); }}')
    dot = _cached_svg("dot", _DOT_SVG.format(color=p.ON_ACCENT))
    if dot:
        rules.append(f'QRadioButton::indicator:checked {{ image: url("{dot}"); }}')
    chevron = _cached_svg("chevron", _CHEVRON_SVG.format(color=p.TEXT_SECONDARY))
    if chevron:
        rules.append(f'QComboBox::down-arrow {{ image: url("{chevron}"); width: 14px; height: 14px; }}')
        rules.append("QComboBox::drop-down { subcontrol-origin: padding; subcontrol-position: center right; "
                     "width: 28px; border: none; }")
    return "".join(rule + "\n" for rule in rules)


def application_stylesheet() -> str:
    """STYLESHEET plus the rules that need files on disk (call with a QApplication)."""
    return STYLESHEET + indicator_qss(PALETTE)
