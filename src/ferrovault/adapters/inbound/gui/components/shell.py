"""Reusable application shell components: top bar and sidebar."""
from __future__ import annotations

from collections.abc import Callable, Iterable
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QMenu, QPushButton, QVBoxLayout

from ..branding import PRODUCT_TAGLINE, PRODUCT_WORDMARK_A, PRODUCT_WORDMARK_B
from ..icons import icon
from ..svg import logo_widget
from ..design.tokens import CONTROL_H_MD, SIDEBAR_W, TOPBAR_H
from ..theme import PALETTE as P
from .cards import HealthCard


class AppTopBar(QFrame):
    """Professional top navigation with a compact brand and primary workflows."""

    def __init__(self, *, primary_actions: Iterable[tuple[str, str, str, Callable]], more_actions: Iterable[tuple[str, Callable]]):
        super().__init__()
        self.setObjectName("topbar")
        self.setFixedHeight(TOPBAR_H)
        row = QHBoxLayout(self)
        row.setContentsMargins(16, 0, 12, 0)
        row.setSpacing(4)

        row.addWidget(logo_widget(28))
        row.addSpacing(6)
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

        # Top-bar actions are neutral; colour is reserved for state.
        color_map = {"accent": P.TEXT_PRIMARY, "signal": P.TEXT_PRIMARY, "muted": P.TEXT_PRIMARY, "text": P.TEXT_PRIMARY}
        for text, icon_name, tone, handler in primary_actions:
            btn = QPushButton(f"  {text}")
            btn.setIcon(icon(icon_name, color_map.get(tone, P.TEXT_PRIMARY), 16))
            btn.setObjectName("topNav")
            btn.setMinimumHeight(CONTROL_H_MD)
            btn.clicked.connect(handler)
            row.addWidget(btn)

        more = QPushButton("  More")
        more.setIcon(icon("sliders", P.TEXT_PRIMARY, 16))
        more.setObjectName("topNav")
        more.setMinimumHeight(CONTROL_H_MD)
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
        self.setFixedWidth(SIDEBAR_W)
        self.nav_buttons: list[tuple[str, QPushButton]] = []
        self.health_card = HealthCard()
        col = QVBoxLayout(self)
        col.setContentsMargins(8, 12, 8, 12)
        col.setSpacing(2)
        for name, icon_name in sections:
            button = QPushButton(f"  {name}")
            button.setIcon(icon(icon_name, P.TEXT_PRIMARY if name == current else P.TEXT_SECONDARY, 18))
            button.setObjectName("sideActive" if name == current else "sideNav")
            button.setMinimumHeight(CONTROL_H_MD)
            button.clicked.connect(lambda _=False, section=name: on_select(section))
            self.nav_buttons.append((name, button))
            col.addWidget(button)

        col.addSpacing(8)
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setObjectName("lineSeparator")
        col.addWidget(line)

        settings = QPushButton("  Settings")
        settings.setIcon(icon("settings", P.TEXT_SECONDARY, 18))
        settings.setObjectName("sideNav")
        settings.setMinimumHeight(CONTROL_H_MD)
        settings.clicked.connect(on_settings)
        col.addWidget(settings)
        col.addStretch()
        self.health_card.setVisible(show_health)
        col.addWidget(self.health_card)

    def set_active(self, section: str) -> None:
        for name, button in self.nav_buttons:
            button.setObjectName("sideActive" if name == section else "sideNav")
            button.setIcon(icon("shield" if name == "Zero Trust" else _icon_for(name), P.TEXT_PRIMARY if name == section else P.TEXT_SECONDARY, 18))
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
