"""Reusable high-level panels for the main AegisVault workspace."""
from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from ..icons import icon
from ..svg import empty_state_widget
from ..theme import ACCENT, DANGER, MUTED, TEXT
from .cards import EntryCard
from .primitives import caption


class VaultListPanel(QFrame):
    """Search, filter, entry-list, and pagination panel.

    The panel owns the Qt widgets needed by the left credential list while
    delegating behavior back to MainWindow through callbacks. Keeping this as a
    component prevents the main window from accumulating layout code every time
    the vault list changes visually.
    """

    def __init__(
        self,
        *,
        on_add: Callable[[], None],
        on_category_menu: Callable[[], None],
        on_toggle_sort: Callable[[], None],
        on_clear_filters: Callable[[], None],
        on_filter_changed: Callable[[], None],
        on_select,
    ):
        super().__init__()
        self.setObjectName("listWrap")
        self.setMinimumWidth(390)
        self.setMaximumWidth(520)

        col = QVBoxLayout(self)
        col.setContentsMargins(16, 16, 16, 16)
        col.setSpacing(14)

        top = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search entries...")
        self.search.addAction(icon("search", MUTED), QLineEdit.LeadingPosition)
        self.search.textChanged.connect(on_filter_changed)
        top.addWidget(self.search, 1)

        self.add_btn = QPushButton("  New")
        self.add_btn.setIcon(icon("add", TEXT, 21))
        self.add_btn.setObjectName("primary")
        self.add_btn.setMinimumHeight(52)
        self.add_btn.clicked.connect(on_add)
        top.addWidget(self.add_btn)
        col.addLayout(top)

        filters = QHBoxLayout()
        self.cat_btn = QPushButton("All categories  ˅")
        self.cat_btn.setObjectName("filterBtn")
        self.cat_btn.clicked.connect(on_category_menu)
        self.sort_btn = QPushButton("Sort by recent  ˅")
        self.sort_btn.setObjectName("filterBtn")
        self.sort_btn.clicked.connect(on_toggle_sort)
        clear_btn = QPushButton()
        clear_btn.setIcon(icon("sliders", MUTED, 20))
        clear_btn.setObjectName("filterBtn")
        clear_btn.setFixedWidth(52)
        clear_btn.clicked.connect(on_clear_filters)
        filters.addWidget(self.cat_btn)
        filters.addWidget(self.sort_btn)
        filters.addWidget(clear_btn)
        col.addLayout(filters)

        self.list = QListWidget()
        self.list.setSpacing(8)
        self.list.currentItemChanged.connect(on_select)
        col.addWidget(self.list, 1)

        foot = QHBoxLayout()
        self.count_lbl = QLabel("0 entries")
        self.count_lbl.setObjectName("muted")
        foot.addWidget(self.count_lbl)
        foot.addStretch()
        self.page_row = QHBoxLayout()
        self.page_row.setSpacing(6)
        foot.addLayout(self.page_row)
        col.addLayout(foot)

    def set_filter_labels(self, category: str, sort: str) -> None:
        self.cat_btn.setText(f"{category}  ˅")
        self.sort_btn.setText("Sort by name  ˅" if sort == "name" else "Sort by recent  ˅")

    def reset_filters(self) -> None:
        self.search.clear()
        self.set_filter_labels("All categories", "recent")

    def clear_entries(self) -> None:
        self.list.clear()

    def add_entry(self, view, *, selected: bool) -> None:
        item = QListWidgetItem()
        item.setData(Qt.UserRole, view)
        card = EntryCard(view, selected=selected)
        item.setSizeHint(card.sizeHint())
        self.list.addItem(item)
        self.list.setItemWidget(item, card)

    def set_count(self, text: str) -> None:
        self.count_lbl.setText(text)

    def render_pagination(self, *, current_page: int, pages: int, on_go_page: Callable[[int], None]) -> None:
        while self.page_row.count():
            widget = self.page_row.takeAt(0).widget()
            if widget:
                widget.deleteLater()

        def mk(label: str, enabled: bool, active: bool, target: int | None) -> None:
            button = QPushButton(label)
            button.setFixedSize(42, 42)
            button.setObjectName("pageActive" if active else "pageBtn")
            button.setEnabled(enabled)
            button.setCursor(Qt.PointingHandCursor)
            if target is not None:
                button.clicked.connect(lambda _=False, x=target: on_go_page(x))
            self.page_row.addWidget(button)

        mk("‹", current_page > 0, False, current_page - 1)
        first = max(0, min(current_page - 2, pages - 5))
        for pnum in range(first, min(pages, first + 5)):
            mk(str(pnum + 1), True, pnum == current_page, pnum)
        mk("›", current_page < pages - 1, False, current_page + 1)

    def refresh_selection(self, selected_name: str | None) -> None:
        for index in range(self.list.count()):
            item = self.list.item(index)
            view = item.data(Qt.UserRole)
            widget = self.list.itemWidget(item)
            if widget:
                widget.setProperty("selected", "true" if view.name == selected_name else "false")
                widget.style().unpolish(widget)
                widget.style().polish(widget)


class EntryDetailPanel(QFrame):
    """Right-side entry/detail canvas.

    It exposes its child widgets because the existing MainWindow owns the
    business logic. The visual tree is now isolated in one reusable component.
    """

    def __init__(
        self,
        *,
        on_reveal: Callable[[], None],
        on_copy: Callable[[], None],
        on_favorite: Callable[[], None],
        on_share: Callable[[], None],
        on_restore: Callable[[], None],
        on_delete: Callable[[], None],
    ):
        super().__init__()
        self.setObjectName("detailPanel")
        panel_layout = QVBoxLayout(self)
        panel_layout.setContentsMargins(0, 0, 0, 0)
        panel_layout.setSpacing(0)

        scroll = QScrollArea()
        scroll.setObjectName("detailScroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        panel_layout.addWidget(scroll)

        body = QWidget()
        body.setObjectName("detailContent")
        layout = QVBoxLayout(body)
        layout.setContentsMargins(32, 28, 32, 28)
        layout.setSpacing(16)
        scroll.setWidget(body)

        self.empty_art = empty_state_widget(80)
        layout.addWidget(self.empty_art, alignment=Qt.AlignHCenter)

        self.empty_card = QFrame()
        self.empty_card.setObjectName("emptyCard")
        ec = QVBoxLayout(self.empty_card)
        ec.setContentsMargins(22, 20, 22, 20)
        ec.setSpacing(8)
        self.name_lbl = QLabel("Select an entry")
        self.name_lbl.setObjectName("h1")
        self.name_lbl.setAlignment(Qt.AlignCenter)
        self.user_lbl = QLabel("Choose an entry from the list to view its details securely.")
        self.user_lbl.setObjectName("muted")
        self.user_lbl.setAlignment(Qt.AlignCenter)
        self.user_lbl.setWordWrap(True)
        self.url_lbl = QLabel("")
        self.url_lbl.setObjectName("muted")
        self.url_lbl.setWordWrap(True)
        ec.addWidget(self.name_lbl)
        ec.addWidget(self.user_lbl)
        ec.addWidget(self.url_lbl)
        layout.addWidget(self.empty_card)

        self.features = QWidget()
        self.features.setObjectName("featureGrid")
        self.features_layout = QVBoxLayout(self.features)
        self.features_layout.setContentsMargins(0, 0, 0, 0)
        self.features_layout.setSpacing(14)
        layout.addWidget(self.features)

        self.content = QFrame()
        self.content.setObjectName("detailCard")
        content_box = QVBoxLayout(self.content)
        content_box.setContentsMargins(24, 22, 24, 22)
        content_box.setSpacing(12)
        content_box.addWidget(caption("SECRET"))
        self.secret_lbl = QLabel("")
        self.secret_lbl.setObjectName("h1")
        self.secret_lbl.setTextInteractionFlags(Qt.TextSelectableByMouse)
        content_box.addWidget(self.secret_lbl)

        secret_actions = QHBoxLayout()
        self.reveal_btn = QPushButton("  Reveal")
        self.reveal_btn.setIcon(icon("eye", TEXT))
        self.reveal_btn.clicked.connect(on_reveal)
        self.copy_btn = QPushButton("  Copy")
        self.copy_btn.setIcon(icon("copy", TEXT))
        self.copy_btn.clicked.connect(on_copy)
        secret_actions.addWidget(self.reveal_btn)
        secret_actions.addWidget(self.copy_btn)
        secret_actions.addStretch()
        content_box.addLayout(secret_actions)

        content_box.addSpacing(10)
        self.totp_title = caption("2FA CODE")
        content_box.addWidget(self.totp_title)
        self.code_lbl = QLabel("------")
        self.code_lbl.setObjectName("code")
        self.code_bar = QProgressBar()
        self.code_bar.setRange(0, 30)
        self.code_bar.setTextVisible(False)
        content_box.addWidget(self.code_lbl)
        content_box.addWidget(self.code_bar)

        action_row = QHBoxLayout()
        self.favorite_btn = QPushButton("  Favorite")
        self.favorite_btn.setIcon(icon("star", ACCENT))
        self.favorite_btn.clicked.connect(on_favorite)
        self.share_btn = QPushButton("  Zero Trust share")
        self.share_btn.setIcon(icon("users", TEXT))
        self.share_btn.clicked.connect(on_share)
        action_row.addWidget(self.favorite_btn)
        action_row.addWidget(self.share_btn)
        content_box.addLayout(action_row)

        self.restore_btn = QPushButton("  Restore entry")
        self.restore_btn.setIcon(icon("rotate", TEXT))
        self.restore_btn.clicked.connect(on_restore)
        content_box.addWidget(self.restore_btn)

        self.del_btn = QPushButton("  Delete entry")
        self.del_btn.setIcon(icon("trash", DANGER))
        self.del_btn.setObjectName("danger")
        self.del_btn.clicked.connect(on_delete)
        content_box.addWidget(self.del_btn)
        layout.addWidget(self.content)
        layout.addStretch(1)

    def set_empty(self, *, section: str, title: str, subtitle: str) -> None:
        self.content.setVisible(False)
        self.features.setVisible(True)
        self.empty_art.setVisible(section not in {"Zero Trust", "Categories"})
        self.name_lbl.setAlignment(Qt.AlignCenter)
        self.user_lbl.setAlignment(Qt.AlignCenter)
        self.name_lbl.setText(title)
        self.user_lbl.setText(subtitle)
        self.url_lbl.setText("")

    def set_entry(self, view) -> None:
        self.content.setVisible(True)
        self.features.setVisible(False)
        self.empty_art.setVisible(False)
        self.name_lbl.setAlignment(Qt.AlignLeft)
        self.user_lbl.setAlignment(Qt.AlignLeft)
        self.name_lbl.setText(view.name)
        self.user_lbl.setText(view.username or "—")

    def set_totp_visible(self, visible: bool) -> None:
        for widget in (self.totp_title, self.code_lbl, self.code_bar):
            widget.setVisible(visible)
