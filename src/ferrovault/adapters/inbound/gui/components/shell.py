"""Reusable application shell components: top bar and sidebar."""
from __future__ import annotations

from collections.abc import Callable, Iterable
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QMenu, QPushButton, QVBoxLayout

from ..branding import PRODUCT_TAGLINE, PRODUCT_WORDMARK_A, PRODUCT_WORDMARK_B
from ..icons import icon
from ..svg import logo_widget
from ..design.tokens import SIDEBAR_WIDTH, TOPBAR_HEIGHT
from ..theme import ACCENT, ACCENT_2, MUTED, TEXT
from .cards import HealthCard


class AppTopBar(QFrame):
    """Professional top navigation with a compact brand and primary workflows."""

    def __init__(self, *, primary_actions: Iterable[tuple[str, str, str, Callable]], more_actions: Iterable[tuple[str, Callable]]):
        super().__init__()
        self.setObjectName("topbar")
        self.setMinimumHeight(TOPBAR_HEIGHT)
        self.setMaximumHeight(TOPBAR_HEIGHT + 8)
        row = QHBoxLayout(self)
        row.setContentsMargins(18, 9, 18, 9)
        row.setSpacing(12)

        row.addWidget(logo_widget(36))
        brand_col = QVBoxLayout()
        brand_col.setSpacing(1)
        brand_line = QHBoxLayout()
        brand_line.setSpacing(0)
        a = QLabel(PRODUCT_WORDMARK_A)
        a.setObjectName("brand")
        b = QLabel(PRODUCT_WORDMARK_B)
        b.setObjectName("brandAccent")
        brand_line.addWidget(a)
        brand_line.addWidget(b)
        brand_line.addStretch()
        tag = QLabel(PRODUCT_TAGLINE)
        tag.setObjectName("tagline")
        brand_col.addStretch()
        brand_col.addLayout(brand_line)
        brand_col.addWidget(tag)
        brand_col.addStretch()
        row.addLayout(brand_col)
        row.addStretch(1)

        color_map = {"accent": ACCENT, "signal": ACCENT_2, "muted": MUTED, "text": TEXT}
        for text, icon_name, tone, handler in primary_actions:
            btn = QPushButton(f"  {text}")
            btn.setIcon(icon(icon_name, color_map.get(tone, MUTED), 18))
            btn.setObjectName("topNav")
            btn.setMinimumHeight(38)
            btn.clicked.connect(handler)
            row.addWidget(btn)

        more = QPushButton("  More")
        more.setIcon(icon("sliders", MUTED, 18))
        more.setObjectName("topNav")
        more.setMinimumHeight(38)
        menu = QMenu(more)
        for text, handler in more_actions:
            action = menu.addAction(text)
            action.triggered.connect(handler)
        more.setMenu(menu)
        row.addWidget(more)


class AppSidebar(QFrame):
    """Reusable left navigation with active-state support."""

    def __init__(self, *, sections: Iterable[tuple[str, str]], current: str, on_select: Callable[[str], None], on_settings: Callable[[], None], show_health: bool):
        super().__init__()
        self.setObjectName("sidebar")
        self.setFixedWidth(SIDEBAR_WIDTH)
        self.nav_buttons: list[tuple[str, QPushButton]] = []
        self.health_card = HealthCard()
        col = QVBoxLayout(self)
        col.setContentsMargins(12, 14, 12, 14)
        col.setSpacing(7)
        for name, icon_name in sections:
            button = QPushButton(f"  {name}")
            button.setIcon(icon(icon_name, TEXT if name == current else MUTED, 20))
            button.setObjectName("sideActive" if name == current else "sideNav")
            button.setMinimumHeight(46)
            button.setStyleSheet("text-align: left;")
            button.clicked.connect(lambda _=False, section=name: on_select(section))
            self.nav_buttons.append((name, button))
            col.addWidget(button)

        col.addSpacing(14)
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setObjectName("lineSeparator")
        col.addWidget(line)

        settings = QPushButton("  Settings")
        settings.setIcon(icon("settings", MUTED, 20))
        settings.setObjectName("sideNav")
        settings.setMinimumHeight(46)
        settings.setStyleSheet("text-align: left;")
        settings.clicked.connect(on_settings)
        col.addWidget(settings)
        col.addStretch()
        self.health_card.setVisible(show_health)
        col.addWidget(self.health_card)

    def set_active(self, section: str) -> None:
        for name, button in self.nav_buttons:
            button.setObjectName("sideActive" if name == section else "sideNav")
            button.setIcon(icon("shield" if name == "Zero Trust" else _icon_for(name), TEXT if name == section else MUTED, 20))
            button.style().unpolish(button)
            button.style().polish(button)


def _icon_for(name: str) -> str:
    return {
        "Vault": "vault",
        "Categories": "grid",
        "Favorites": "star",
        "Zero Trust": "shield",
        "Shared": "users",
        "Trash": "trash",
    }.get(name, "vault")
