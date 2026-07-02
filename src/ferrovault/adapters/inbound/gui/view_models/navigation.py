"""Qt-free navigation state for the desktop GUI shell.

The main window should render screens; it should not own the rules for which
sections are dashboards, which sections reset filters, or what empty-state copy
belongs to each route.  This small router keeps those decisions centralized and
makes section switching testable without PySide6.
"""
from __future__ import annotations

from dataclasses import dataclass

VALID_SECTIONS = ("Vault", "Categories", "Favorites", "Zero Trust", "Shared", "Trash")
DASHBOARD_SECTIONS = frozenset({"Categories", "Zero Trust"})
DEFAULT_SECTION = "Vault"
ALL_CATEGORY_LABEL = "All categories"


@dataclass(frozen=True)
class EmptyStateModel:
    """Content shown in the detail pane when no entry is selected."""

    title: str
    subtitle: str
    show_art: bool = True


@dataclass(frozen=True)
class NavigationRoute:
    """Normalized route plus the rendering side-effects the shell needs."""

    section: str
    is_dashboard: bool
    reset_category_filter: bool
    clear_selection: bool
    refresh_overview: bool
    empty_state: EmptyStateModel


@dataclass(frozen=True)
class CategoryDrilldown:
    """Navigation event emitted when a category card opens a filtered vault."""

    section: str
    category: str
    clear_selection: bool
    empty_state: EmptyStateModel


class AppNavigationRouter:
    """Tiny stateful router for the AegisVault desktop shell.

    It intentionally has no Qt dependency.  MainWindow asks this router what a
    navigation event means, then performs the concrete widget updates.
    """

    def __init__(self, *, initial_section: str = DEFAULT_SECTION):
        self._section = _normalize_section(initial_section)

    @property
    def section(self) -> str:
        return self._section

    def navigate(self, section: str) -> NavigationRoute:
        self._section = _normalize_section(section)
        dashboard = self._section in DASHBOARD_SECTIONS
        return NavigationRoute(
            section=self._section,
            is_dashboard=dashboard,
            reset_category_filter=dashboard,
            clear_selection=dashboard,
            refresh_overview=dashboard,
            empty_state=self.empty_state_for(self._section),
        )

    def open_category(self, category: str) -> CategoryDrilldown:
        self._section = DEFAULT_SECTION
        return CategoryDrilldown(
            section=DEFAULT_SECTION,
            category=(category or ALL_CATEGORY_LABEL),
            clear_selection=True,
            empty_state=self.empty_state_for(DEFAULT_SECTION),
        )

    def empty_state_for(self, section: str | None = None) -> EmptyStateModel:
        section = _normalize_section(section or self._section)
        if section == "Zero Trust":
            return EmptyStateModel(
                title="Zero Trust control plane",
                subtitle=(
                    "Every reveal, copy, share, export, and rotation is evaluated "
                    "by identity, device, policy, and audit posture."
                ),
                show_art=False,
            )
        if section == "Categories":
            return EmptyStateModel(
                title="Smart collections",
                subtitle=(
                    "Browse by project, website, environment, team, or platform "
                    "with cached web favicons."
                ),
                show_art=False,
            )
        if section == "Trash":
            return EmptyStateModel(
                title="Trash",
                subtitle="Restore deleted entries or permanently remove records from the vault.",
            )
        if section == "Shared":
            return EmptyStateModel(
                title="Shared access",
                subtitle="Review entries with active or revoked Zero Trust crypto grants.",
            )
        if section == "Favorites":
            return EmptyStateModel(
                title="Favorites",
                subtitle="Pinned secrets appear here for fast access.",
            )
        return EmptyStateModel(
            title="Select an entry",
            subtitle="Choose an entry from the list\nto view its details securely.",
        )


def _normalize_section(section: str | None) -> str:
    section = section or DEFAULT_SECTION
    return section if section in VALID_SECTIONS else DEFAULT_SECTION
