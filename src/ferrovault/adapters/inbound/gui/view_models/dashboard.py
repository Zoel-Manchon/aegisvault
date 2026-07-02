"""Qt-free dashboard models for the desktop GUI.

The main window owns application state and controllers, but dashboard copy,
metrics, and card payloads should be testable without Qt.  Renderers consume
these models to build widgets.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable


@dataclass(frozen=True)
class DashboardMetric:
    """One compact metric tile on a dashboard."""

    label: str
    value: str
    helper: str
    tone: str = "neutral"


@dataclass(frozen=True)
class CategoryCardModel:
    """Presentation model for a category/collection card."""

    name: str
    count: int
    favorites: int
    twofa: int
    shared: int
    top_url: str = ""


@dataclass(frozen=True)
class VaultDashboardModel:
    """Right-side vault/category dashboard model."""

    metrics: tuple[DashboardMetric, ...]
    categories: tuple[CategoryCardModel, ...]
    empty_title: str
    empty_body: str


DEFAULT_EMPTY_TITLE = "No categories yet"
DEFAULT_EMPTY_BODY = (
    "Add categories like Infrastructure, Cloud, Databases, Personal, or "
    "Production to make the vault feel organized and enterprise-ready."
)


def build_vault_dashboard_model(overview: Any) -> VaultDashboardModel:
    """Translate a vault overview aggregate into renderer-ready UI models."""

    categories = tuple(
        CategoryCardModel(
            name=str(category.name),
            count=int(category.count),
            favorites=int(category.favorites),
            twofa=int(category.twofa),
            shared=int(category.shared),
            top_url=str(getattr(category, "top_url", "") or ""),
        )
        for category in tuple(getattr(overview, "categories", ()))
    )
    return VaultDashboardModel(
        metrics=(
            DashboardMetric("Vault items", str(getattr(overview, "total", 0)), "active secrets"),
            DashboardMetric("Favorites", str(getattr(overview, "favorites", 0)), "pinned for fast access"),
            DashboardMetric("2FA enabled", str(getattr(overview, "twofa", 0)), "entries with TOTP seeds"),
            DashboardMetric("Shared", str(getattr(overview, "shared", 0)), "records marked for teams"),
        ),
        categories=categories,
        empty_title=DEFAULT_EMPTY_TITLE,
        empty_body=DEFAULT_EMPTY_BODY,
    )


def grid_rows(items: Iterable[Any], *, columns: int = 2) -> tuple[tuple[int, int, Any], ...]:
    """Return stable row/column positions for dashboard grids."""

    columns = max(1, int(columns))
    return tuple((index // columns, index % columns, item) for index, item in enumerate(tuple(items)))
