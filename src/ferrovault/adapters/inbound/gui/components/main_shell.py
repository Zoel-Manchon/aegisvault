"""Composable main shell for the AegisVault desktop window."""
from __future__ import annotations

from collections.abc import Callable, Iterable

from PySide6.QtWidgets import QHBoxLayout, QVBoxLayout, QWidget

from .panels import EntryDetailPanel, VaultListPanel
from .shell import AppSidebar, AppTopBar


class MainShellView(QWidget):
    """Owns the top-level visual composition of the desktop application.

    The MainWindow now wires session state/controllers into this shell instead
    of building the header, sidebar, list, and detail panel inline.
    """

    def __init__(
        self,
        *,
        primary_actions: Iterable[tuple[str, str, str, Callable]],
        more_actions: Iterable[tuple[str, Callable]],
        sections: Iterable[tuple[str, str]],
        current_section: str,
        show_health: bool,
        on_section_select: Callable[[str], None],
        on_settings: Callable[[], None],
        list_callbacks: dict[str, Callable],
        detail_callbacks: dict[str, Callable],
    ):
        super().__init__()
        self.setObjectName("appShell")

        outer = QVBoxLayout(self)
        outer.setContentsMargins(18, 18, 18, 18)
        outer.setSpacing(14)

        self.top_bar = AppTopBar(primary_actions=primary_actions, more_actions=more_actions)
        outer.addWidget(self.top_bar)

        main = QHBoxLayout()
        main.setSpacing(14)
        self.sidebar = AppSidebar(
            sections=sections,
            current=current_section,
            on_select=on_section_select,
            on_settings=on_settings,
            show_health=show_health,
        )
        self.list_panel = VaultListPanel(**list_callbacks)
        self.detail_panel = EntryDetailPanel(**detail_callbacks)
        main.addWidget(self.sidebar)
        main.addWidget(self.list_panel, 5)
        main.addWidget(self.detail_panel, 7)
        outer.addLayout(main, 1)
