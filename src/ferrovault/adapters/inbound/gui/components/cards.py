"""Reusable cards for entries, categories, metrics, and health status."""
from __future__ import annotations

from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout

from ..favicons import favicon_icon, favicon_pixmap
from ..icons import icon
from ..theme import ACCENT, GOOD, MUTED, TEXT
from .primitives import MetricCard


def entry_subtitle(view) -> str:
    category = getattr(view, "category", "") or ""
    if not category:
        tags = [t for t in getattr(view, "tags", []) if t]
        category = tags[0] if tags else ""
    kind = category.capitalize() if category else "Account"
    username = getattr(view, "username", "") or "Credential"
    return f"{kind} · {username}"


def initials(name: str) -> str:
    parts = [p for p in name.replace("-", " ").replace("_", " ").split() if p]
    if not parts:
        return "AV"
    if len(parts) == 1:
        return parts[0][:2].upper()
    return (parts[0][0] + parts[1][0]).upper()


class EntryCard(QFrame):
    """Left-list credential card with favicon/initial fallback."""

    def __init__(self, view, selected: bool = False):
        super().__init__()
        self.setObjectName("entryCard")
        self.setProperty("selected", "true" if selected else "false")
        self.setMinimumHeight(74)
        row = QHBoxLayout(self)
        row.setContentsMargins(14, 10, 14, 10)
        row.setSpacing(12)

        avatar = QLabel()
        avatar.setFixedSize(42, 42)
        avatar.setAlignment(Qt.AlignCenter)
        avatar.setPixmap(favicon_pixmap(getattr(view, "url", ""), initials(view.name), 42))
        avatar.setStyleSheet("background: transparent; border: none;")
        row.addWidget(avatar)

        texts = QVBoxLayout()
        name = QLabel(view.name)
        name.setObjectName("h2")
        sub = QLabel(entry_subtitle(view))
        sub.setObjectName("smallMuted")
        texts.addStretch()
        texts.addWidget(name)
        texts.addWidget(sub)
        texts.addStretch()
        row.addLayout(texts, 1)

        star = QLabel("★" if getattr(view, "favorite", False) else "☆")
        star.setStyleSheet(f"color: {ACCENT}; font-size: 22px; background: transparent;")
        row.addWidget(star)
        dots = QLabel("•••")
        dots.setStyleSheet(f"color: {MUTED}; font-size: 18px; letter-spacing: 2px; background: transparent;")
        row.addWidget(dots)


class CategoryCard(QPushButton):
    """Clickable collection card with favicon and compact metadata."""

    def __init__(self, name: str, count: int, favorites: int, twofa: int, shared: int, top_url: str = ""):
        plural = "item" if count == 1 else "items"
        meta = f"{count} {plural}  ·  {favorites} favorite{'s' if favorites != 1 else ''}  ·  {twofa} 2FA"
        if shared:
            meta += f"  ·  {shared} shared"
        super().__init__(f"{name}\n{meta}\nOpen collection →")
        self.setObjectName("categoryCard")
        self.setCursor(Qt.PointingHandCursor)
        self.setMinimumHeight(108)
        self.setIcon(favicon_icon(top_url, name, 34) if top_url else icon("grid", ACCENT, 28))
        self.setIconSize(QSize(34, 34))


class HealthCard(QFrame):
    """Sidebar vault-health card."""

    def __init__(self, title: str = "All good", helper: str = "Your vault is healthy"):
        super().__init__()
        self.setObjectName("healthCard")
        row = QHBoxLayout(self)
        row.setContentsMargins(14, 12, 14, 12)
        row.setSpacing(10)
        shield = QLabel()
        shield.setPixmap(icon("shield", GOOD, 26).pixmap(26, 26))
        row.addWidget(shield)
        txt = QVBoxLayout()
        ok = QLabel(title)
        ok.setObjectName("h2")
        sub = QLabel(helper)
        sub.setObjectName("smallMuted")
        txt.addWidget(ok)
        txt.addWidget(sub)
        row.addLayout(txt)


# Backward-compatible class name used by MainWindow.
MetricTile = MetricCard
