"""Presentation pieces of the main window (board 09): top bar, sidebar, list, detail.

These widgets only render data and report user intent through callbacks;
``main_window.MainWindow`` owns the session, policies and security timers.
"""
from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass, field

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView, QFrame, QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QMenu, QProgressBar,
    QPushButton, QScrollArea, QSizePolicy, QStackedWidget, QVBoxLayout, QWidget,
)

from ..design.tokens import COMPACT_BELOW_W, ENTRY_ROW_H, SIDEBAR_W, TOPBAR_H
from ..fmt import KIND_LABELS, SECRET_LABELS, USER_LABELS, host_of
from ..icons import icon, pixmap
from ..theme import PALETTE as P
from .kit import (
    Avatar, Badge, Button, Chip, Kbd, LockPill, Ring, SearchField, clear_layout, hline, icon_button,
    icon_label, label, repolish, set_prop, tone_color, vline,
)

MASK = "•" * 16


# ---- top bar ------------------------------------------------------------------
class TopBar(QFrame):
    """Brand, vault switcher, command search, actions, lock state and "Bloquear ahora"."""

    def __init__(self, vault_name: str, vault_menu: QMenu, on_palette: Callable,
                 actions: Iterable[tuple[str, str, Callable]], more_menu: QMenu, on_lock: Callable):
        super().__init__()
        self.setObjectName("topbar")
        self.setFixedHeight(TOPBAR_H)
        row = QHBoxLayout(self)
        row.setContentsMargins(16, 0, 12, 0)
        row.setSpacing(8)

        brand = QWidget()
        brand.setObjectName("transparent")
        brand.setFixedWidth(SIDEBAR_W - 16 - 8)
        b = QHBoxLayout(brand)
        b.setContentsMargins(0, 0, 0, 0)
        b.setSpacing(8)
        b.addWidget(icon_label("logo", P.ACCENT, 22))
        name = label("AegisVault", "bodyStrong")
        name.setStyleSheet("font-weight: 600; background: transparent;")
        b.addWidget(name)
        self.vault_btn = QPushButton(vault_name)
        self.vault_btn.setObjectName("vaultSwitch")
        self.vault_btn.setIcon(icon("chevron-down", P.TEXT_SECONDARY, 14))
        self.vault_btn.setLayoutDirection(Qt.RightToLeft)
        self.vault_btn.setMenu(vault_menu)
        self.vault_btn.setToolTip("Cambiar de bóveda")
        self.vault_btn.setAccessibleName(f"Cambiar de bóveda: {vault_name}")
        b.addWidget(self.vault_btn)
        b.addStretch(1)
        row.addWidget(brand)

        self.search_btn = Button("Comando o búsqueda…", "search", "search", shortcut="Ctrl K")
        self.search_btn.setFixedWidth(296)
        self.search_btn.setAccessibleName("Abrir la paleta de comandos")
        self.search_btn.clicked.connect(lambda _=False: on_palette())
        # left-align the inner row of the search trigger
        inner = self.search_btn.layout()
        if inner is not None:
            inner.takeAt(0)
            inner.setContentsMargins(10, 0, 6, 0)
            inner.insertStretch(2, 1)
            inner.takeAt(inner.count() - 1)
        row.addWidget(self.search_btn)
        row.addStretch(1)

        nav = QHBoxLayout()
        nav.setSpacing(2)
        self._action_buttons: list[tuple[QPushButton, str]] = []
        for text, icon_name, handler in actions:
            btn = Button(text, "nav", icon_name, on_click=handler)
            btn.setToolTip(text)
            self._action_buttons.append((btn, text))
            nav.addWidget(btn)
        self.more_btn = Button("Más", "nav", "more")
        self.more_btn.setMenu(more_menu)
        self._action_buttons.append((self.more_btn, "Más"))
        nav.addWidget(self.more_btn)
        row.addLayout(nav)
        row.addSpacing(4)
        row.addWidget(vline())
        row.addSpacing(4)
        self.lock_pill = LockPill()
        row.addWidget(self.lock_pill)
        self.lock_btn = Button("Bloquear ahora", "secondary", "lock", on_click=on_lock, tooltip="Bloquear ahora (Ctrl+L)")
        row.addWidget(self.lock_btn)

    def set_compact(self, compact: bool) -> None:
        """Below COMPACT_BELOW_W the actions keep only their icons."""
        for btn, text in self._action_buttons:
            btn.setText("" if compact else text)
        self.search_btn.setFixedWidth(220 if compact else 296)


# ---- sidebar ------------------------------------------------------------------
class NavItem(QPushButton):
    """Sidebar row: icon, label and a count on the right."""

    def __init__(self, text: str, icon_name: str, count: int | None = None, indent: bool = False):
        super().__init__()
        self.setObjectName("navItem")
        self.setCursor(Qt.PointingHandCursor)
        self.setAccessibleName(text)
        self._icon_name = icon_name
        row = QHBoxLayout(self)
        row.setContentsMargins(12 if not indent else 16, 0, 12, 0)
        row.setSpacing(12)
        self._icon = QLabel()
        self._icon.setFixedSize(18, 18)
        self.text_label = QLabel(text)
        self.text_label.setObjectName("navText")
        self.count_label = QLabel("")
        self.count_label.setObjectName("navCount")
        row.addWidget(self._icon)
        row.addWidget(self.text_label, 1)
        row.addWidget(self.count_label)
        for child in (self._icon, self.text_label, self.count_label):
            child.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.setFixedHeight(40 if not indent else 38)
        self.set_count(count)
        self.set_active(False)

    def set_count(self, count: int | None) -> None:
        self.count_label.setText("" if count is None else str(count))

    def set_active(self, active: bool) -> None:
        self._icon.setPixmap(pixmap(self._icon_name, P.TEXT_PRIMARY if active else P.TEXT_SECONDARY, 18))
        if self.property("active") != active:
            self.setProperty("active", active)
            self.text_label.setProperty("active", active)
            repolish(self)


class HealthCard(QFrame):
    clicked = Signal()

    def __init__(self):
        super().__init__()
        self.setObjectName("healthCard")
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip("Abrir el panel de salud")
        col = QVBoxLayout(self)
        col.setContentsMargins(14, 12, 14, 12)
        col.setSpacing(10)
        top = QHBoxLayout()
        top.setSpacing(4)
        title = label("Salud de la bóveda", "secondary")
        title.setStyleSheet("font-size: 13px; background: transparent;")
        top.addWidget(title)
        top.addStretch(1)
        self.score = label("—", "title")
        self.score.setStyleSheet("font-size: 20px; font-weight: 600; background: transparent;")
        top.addWidget(self.score)
        top.addWidget(label("/100", "tertiary"))
        col.addLayout(top)
        self.bar = QProgressBar()
        self.bar.setRange(0, 100)
        self.bar.setTextVisible(False)
        col.addWidget(self.bar)
        self.note_row = QHBoxLayout()
        self.note_row.setSpacing(6)
        self.note_icon = QLabel()
        self.note_icon.setFixedSize(14, 14)
        self.note = QLabel("Calculando…")
        self.note.setStyleSheet(f"color: {P.TEXT_TERTIARY}; font-size: 13px; background: transparent;")
        self.note_row.addWidget(self.note_icon)
        self.note_row.addWidget(self.note, 1)
        col.addLayout(self.note_row)

    def set_report(self, score: int | None, warnings: int = 0) -> None:
        if score is None:
            self.score.setText("—")
            self.bar.setValue(0)
            self.note.setText("Calculando…")
            self.note_icon.clear()
            return
        tone = "success" if score >= 80 else ("warning" if score >= 50 else "danger")
        self.score.setText(str(score))
        self.bar.setValue(score)
        set_prop(self.bar, "tone", tone)
        if warnings:
            text = "1 aviso por revisar" if warnings == 1 else f"{warnings} avisos por revisar"
            note_tone = "warning"
        else:
            text, note_tone = "Todo en orden", "success"
        color = tone_color(note_tone)
        self.note.setText(text)
        self.note.setStyleSheet(f"color: {color}; font-size: 13px; background: transparent;")
        self.note_icon.setPixmap(pixmap("warning" if warnings else "check", color, 14, 2.0))

    def mouseReleaseEvent(self, event):  # noqa: N802 - Qt API
        if event.button() == Qt.LeftButton:
            self.clicked.emit()
        super().mouseReleaseEvent(event)


class Sidebar(QFrame):
    section_selected = Signal(str)
    category_selected = Signal(str)
    zero_trust = Signal()
    health = Signal()
    settings = Signal()
    new_category = Signal()

    def __init__(self):
        super().__init__()
        self.setObjectName("sidebar")
        self.setFixedWidth(SIDEBAR_W)
        col = QVBoxLayout(self)
        col.setContentsMargins(10, 12, 10, 12)
        col.setSpacing(2)
        self.vault_item = NavItem("Bóveda", "vault")
        self.vault_item.clicked.connect(lambda: self.section_selected.emit("Vault"))
        col.addWidget(self.vault_item)
        col.addSpacing(14)
        head = QHBoxLayout()
        head.setContentsMargins(10, 0, 4, 0)
        head.addWidget(label("CATEGORÍAS", "overline"))
        head.addStretch(1)
        add = icon_button("add", "Nueva categoría", self.new_category.emit, 16)
        add.setFixedSize(28, 28)
        head.addWidget(add)
        col.addLayout(head)
        col.addSpacing(4)
        self._cat_box = QVBoxLayout()
        self._cat_box.setSpacing(2)
        col.addLayout(self._cat_box)
        self._cat_items: dict[str, NavItem] = {}
        col.addSpacing(8)
        col.addWidget(hline())
        col.addSpacing(8)
        self.fav_item = NavItem("Favoritos", "star")
        self.fav_item.clicked.connect(lambda: self.section_selected.emit("Favorites"))
        self.zt_item = NavItem("Zero Trust", "shield")
        self.zt_item.clicked.connect(self.zero_trust.emit)
        self.shared_item = NavItem("Compartidos", "users")
        self.shared_item.clicked.connect(lambda: self.section_selected.emit("Shared"))
        self.trash_item = NavItem("Papelera", "trash")
        self.trash_item.clicked.connect(lambda: self.section_selected.emit("Trash"))
        for item in (self.fav_item, self.zt_item, self.shared_item, self.trash_item):
            col.addWidget(item)
        col.addStretch(1)
        self.health_card = HealthCard()
        self.health_card.clicked.connect(self.health.emit)
        col.addWidget(self.health_card)
        col.addSpacing(10)
        self.settings_item = NavItem("Ajustes", "settings")
        self.settings_item.clicked.connect(self.settings.emit)
        col.addWidget(self.settings_item)
        self._sections = {"Vault": self.vault_item, "Favorites": self.fav_item,
                          "Shared": self.shared_item, "Trash": self.trash_item}

    def set_counts(self, total: int, favorites: int, shared: int, trash: int) -> None:
        self.vault_item.set_count(total)
        self.fav_item.set_count(favorites)
        self.shared_item.set_count(shared or None)
        self.trash_item.set_count(trash or None)

    def set_categories(self, categories: Iterable[tuple[str, int]]) -> None:
        clear_layout(self._cat_box)
        self._cat_items = {}
        cats = list(categories)
        for name, count in cats:
            item = NavItem(name, "folder", count, indent=True)
            item.clicked.connect(lambda _=False, c=name: self.category_selected.emit(c))
            self._cat_box.addWidget(item)
            self._cat_items[name] = item
        if not cats:
            hint = label("Las categorías salen de tus entradas.", "tertiary", wrap=True)
            hint.setContentsMargins(16, 2, 8, 2)
            self._cat_box.addWidget(hint)

    def set_active(self, section: str, category: str | None = None) -> None:
        for key, item in self._sections.items():
            item.set_active(key == section and not category)
        for name, item in self._cat_items.items():
            item.set_active(bool(category) and name == category)


# ---- list -----------------------------------------------------------------------
@dataclass(frozen=True)
class RowAlert:
    tone: str          # warning | danger
    short: str         # "Reutilizada"
    title: str         # banner lead
    text: str          # banner text
    action: str        # banner button
    action_key: str    # what the button does


class EntryRow(QFrame):
    """60 px card of the list: letter tile, name, user, alert badge, 2FA, favourite."""

    def __init__(self, view, alert: RowAlert | None = None, trash_days_left: int | None = None):
        super().__init__()
        self.setObjectName("entryCard")
        self.view = view
        self.setFixedHeight(ENTRY_ROW_H)
        deleted = bool(getattr(view, "deleted", False))
        if deleted:
            self.setProperty("deleted", True)
        row = QHBoxLayout(self)
        row.setContentsMargins(12, 0, 12, 0)
        row.setSpacing(12)
        row.addWidget(Avatar(view.name, "md", muted=deleted))
        texts = QVBoxLayout()
        texts.setSpacing(1)
        texts.addStretch(1)
        self.title = label(view.name, "rowTitle")
        sub_text = _row_subtitle(view)
        if deleted:
            sub_text = (f"Se borra en {trash_days_left} días" if trash_days_left is not None and trash_days_left > 0
                        else "En la papelera")
        self.sub = label(sub_text, "rowSub")
        if deleted:
            self.title.setProperty("muted", True)
            self.sub.setProperty("muted", True)
        texts.addWidget(self.title)
        texts.addWidget(self.sub)
        texts.addStretch(1)
        row.addLayout(texts, 1)
        if alert is not None and not deleted:
            row.addWidget(Badge(alert.short, alert.tone))
        if getattr(view, "has_totp", False) and not deleted:
            row.addWidget(Badge("2FA", "mono", ""))
        if getattr(view, "favorite", False) and not deleted:
            star = icon_label("star-filled", P.ACCENT, 16)
            star.setToolTip("Favorito")
            row.addWidget(star)
        if deleted:
            row.addWidget(icon_label("trash", P.TEXT_TERTIARY, 16))
        self.setAccessibleName(f"{view.name}, {sub_text}")

    def set_selected(self, selected: bool) -> None:
        set_prop(self, "selected", bool(selected))


def _row_subtitle(view) -> str:
    kind = getattr(view, "kind", "login") or "login"
    user = getattr(view, "username", "") or ""
    if kind == "note":
        return "Nota segura"
    if kind == "card":
        return user or "Tarjeta"
    if kind == "api_key":
        return user or "API key"
    return user or host_of(getattr(view, "url", "")) or "Sin usuario"


class EntryList(QListWidget):
    """Keyboard-first list: arrows move, Enter opens the editor, Supr trashes."""

    activated_entry = Signal(object)
    delete_requested = Signal(object)
    menu_requested = Signal(object, object)   # view, global pos

    def __init__(self):
        super().__init__()
        self.setSelectionMode(QAbstractItemView.SingleSelection)
        self.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.setSpacing(2)
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self._context)
        self.setAccessibleName("Lista de entradas")

    def current_view(self):
        item = self.currentItem()
        return item.data(Qt.UserRole) if item is not None else None

    def _context(self, pos):
        item = self.itemAt(pos)
        if item is None:
            return
        self.setCurrentItem(item)
        self.menu_requested.emit(item.data(Qt.UserRole), self.viewport().mapToGlobal(pos))

    def keyPressEvent(self, event):  # noqa: N802 - Qt API
        view = self.current_view()
        if view is not None and event.key() in (Qt.Key_Return, Qt.Key_Enter):
            self.activated_entry.emit(view)
            return
        if view is not None and event.key() == Qt.Key_Delete:
            self.delete_requested.emit(view)
            return
        if view is not None and event.key() == Qt.Key_F10 and event.modifiers() & Qt.ShiftModifier:
            rect = self.visualItemRect(self.currentItem())
            self.menu_requested.emit(view, self.viewport().mapToGlobal(rect.center()))
            return
        super().keyPressEvent(event)


class ListPanel(QFrame):
    """Header, search, filters, the entry list (or an empty state) and paging."""

    def __init__(self, *, on_new: Callable, on_search: Callable[[str], None], on_select: Callable,
                 on_page: Callable[[int], None], category_menu: QMenu, sort_menu: QMenu,
                 on_clear_category: Callable):
        super().__init__()
        self.setObjectName("listWrap")
        self.setMinimumWidth(340)
        self.setMaximumWidth(420)
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
        col = QVBoxLayout(self)
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(0)

        top = QVBoxLayout()
        top.setContentsMargins(20, 18, 16, 12)
        top.setSpacing(12)
        head = QHBoxLayout()
        head.setSpacing(8)
        self.title = label("Bóveda", "title")
        self.count = label("", "secondary")
        head.addWidget(self.title)
        head.addWidget(self.count, 0, Qt.AlignVCenter)
        head.addStretch(1)
        self.new_btn = Button("Nueva", "primary", "add", on_click=on_new, tooltip="Nueva entrada (Ctrl+N)")
        head.addWidget(self.new_btn)
        self._head = head
        top.addLayout(head)
        self.search = SearchField("Buscar por nombre, usuario o etiqueta", "Ctrl F")
        self.search.setAccessibleName("Buscar en la bóveda")
        self.search.textChanged.connect(on_search)
        top.addWidget(self.search)
        filters = QHBoxLayout()
        filters.setSpacing(8)
        self.cat_btn = Button("Todas las categorías", "dropdown", "filter", trailing_icon="chevron-down")
        self.cat_btn.setMenu(category_menu)
        self.sort_btn = Button("Recientes", "dropdown", "sort", trailing_icon="chevron-down")
        self.sort_btn.setMenu(sort_menu)
        filters.addWidget(self.cat_btn, 3)
        filters.addWidget(self.sort_btn, 2)
        top.addLayout(filters)
        self.chip_row = QHBoxLayout()
        self.chip_row.setSpacing(6)
        top.addLayout(self.chip_row)
        self._on_clear_category = on_clear_category
        col.addLayout(top)

        self.stack = QStackedWidget()
        self.list = EntryList()
        self.list.currentItemChanged.connect(lambda cur, _prev: on_select(cur.data(Qt.UserRole) if cur else None))
        list_wrap = QWidget()
        list_wrap.setObjectName("transparent")
        lw = QVBoxLayout(list_wrap)
        lw.setContentsMargins(10, 0, 10, 0)
        lw.addWidget(self.list)
        self.stack.addWidget(list_wrap)
        self._empty_holder = QWidget()
        self._empty_holder.setObjectName("transparent")
        self._empty_layout = QVBoxLayout(self._empty_holder)
        self._empty_layout.setContentsMargins(0, 0, 0, 0)
        self.stack.addWidget(self._empty_holder)
        col.addWidget(self.stack, 1)

        foot = QFrame()
        foot.setObjectName("dialogFooter")
        f = QHBoxLayout(foot)
        f.setContentsMargins(20, 10, 12, 10)
        self.footer = label("", "secondary")
        f.addWidget(self.footer, 1)
        self.prev_btn = icon_button("chevron-left", "Página anterior", lambda: on_page(-1), 18)
        self.next_btn = icon_button("chevron-right", "Página siguiente", lambda: on_page(+1), 18)
        f.addWidget(self.prev_btn)
        f.addWidget(self.next_btn)
        col.addWidget(foot)
        self._rows: dict[str, EntryRow] = {}

    def add_header_widget(self, widget: QWidget) -> None:
        """Extra action next to "Nueva" (e.g. "Vaciar papelera" in the trash)."""
        self._head.addWidget(widget)

    # rendering
    def set_header(self, title: str, count_text: str) -> None:
        self.title.setText(title)
        self.count.setText(count_text)

    def set_category_chip(self, category: str | None) -> None:
        clear_layout(self.chip_row)
        if category:
            chip = Chip(f"Categoría: {category}", removable=True)
            chip.removed.connect(self._on_clear_category)
            self.chip_row.addWidget(chip)
            self.chip_row.addStretch(1)

    def set_rows(self, views, selected: str | None, alerts: dict, trash_left: dict) -> None:
        self.list.blockSignals(True)
        self.list.clear()
        self._rows = {}
        current_item = None
        for view in views:
            item = QListWidgetItem()
            item.setData(Qt.UserRole, view)
            item.setSizeHint(QSize(10, ENTRY_ROW_H))
            row = EntryRow(view, alerts.get(view.name), trash_left.get(view.name))
            self.list.addItem(item)
            self.list.setItemWidget(item, row)
            self._rows[view.name] = row
            if view.name == selected:
                current_item = item
        if current_item is not None:
            self.list.setCurrentItem(current_item)
        self.list.blockSignals(False)
        self.refresh_selection(selected)
        self.stack.setCurrentIndex(0)

    def refresh_selection(self, selected: str | None) -> None:
        for name, row in self._rows.items():
            row.set_selected(name == selected)

    def show_empty(self, widget: QWidget) -> None:
        clear_layout(self._empty_layout)
        self._empty_layout.addWidget(widget)
        self.stack.setCurrentIndex(1)

    def set_footer(self, text: str, has_prev: bool, has_next: bool) -> None:
        self.footer.setText(text)
        self.prev_btn.setEnabled(has_prev)
        self.next_btn.setEnabled(has_next)
        self.prev_btn.setVisible(has_prev or has_next)
        self.next_btn.setVisible(has_prev or has_next)


# ---- detail -----------------------------------------------------------------------
@dataclass
class DetailModel:
    view: object
    changed_text: str = ""
    alert: RowAlert | None = None
    strength: object | None = None
    history: list = field(default_factory=list)       # [(text, date)]
    trash_days_left: int | None = None


class DetailPanel(QFrame):
    """Right column. Rebuilt for every selection; exposes the live widgets."""

    def __init__(self):
        super().__init__()
        self.setObjectName("detailPanel")
        col = QVBoxLayout(self)
        col.setContentsMargins(0, 0, 0, 0)
        self.scroll = QScrollArea()
        self.scroll.setObjectName("detailScroll")
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        col.addWidget(self.scroll)
        self.secret_lbl = QLabel(MASK)
        self.code_lbl = QLabel("")
        self.reveal_btn = None
        self.hide_hint = None
        self.ring = None
        self.code_hint = None

    def show_placeholder(self, title: str, text: str, icon_name: str = "vault") -> None:
        from .kit import EmptyState
        holder = QWidget()
        holder.setObjectName("detailContent")
        lay = QVBoxLayout(holder)
        lay.addWidget(EmptyState(icon_name, title, text))
        self.scroll.setWidget(holder)
        self.secret_lbl = QLabel(MASK)
        self.code_lbl = QLabel("")
        self.reveal_btn = None
        self.ring = None

    def show_entry(self, model: DetailModel, cb: dict[str, Callable]) -> None:
        view = model.view
        kind = getattr(view, "kind", "login") or "login"
        deleted = bool(getattr(view, "deleted", False))
        content = QWidget()
        content.setObjectName("detailContent")
        col = QVBoxLayout(content)
        col.setContentsMargins(36, 28, 36, 32)
        col.setSpacing(16)

        # header
        head = QHBoxLayout()
        head.setSpacing(16)
        head.addWidget(Avatar(view.name, "lg", muted=deleted), 0, Qt.AlignTop)
        titles = QVBoxLayout()
        titles.setSpacing(6)
        name = label(view.name, "titleLg", selectable=True)
        name.setAccessibleName(f"Entrada {view.name}")
        titles.addWidget(name)
        meta = QHBoxLayout()
        meta.setSpacing(10)
        if getattr(view, "category", ""):
            meta.addWidget(Chip(view.category, "folder"))
        if kind != "login":
            meta.addWidget(Chip(KIND_LABELS.get(kind, kind), {"api_key": "code", "note": "note", "card": "card"}.get(kind)))
        if model.changed_text:
            meta.addWidget(label(model.changed_text, "tertiary"))
        meta.addStretch(1)
        titles.addLayout(meta)
        head.addLayout(titles, 1)
        if not deleted:
            fav = icon_button("star-filled" if getattr(view, "favorite", False) else "star",
                              "Quitar de favoritos" if getattr(view, "favorite", False) else "Añadir a favoritos",
                              cb["favorite"], 20, P.ACCENT if getattr(view, "favorite", False) else P.TEXT_SECONDARY)
            head.addWidget(fav, 0, Qt.AlignTop)
            edit = Button("Editar", "secondary", "edit", on_click=cb["edit"], tooltip="Editar (Ctrl+E)")
            head.addWidget(edit, 0, Qt.AlignTop)
        more = icon_button("more", "Más acciones", None, 20)
        more.clicked.connect(lambda: cb["menu"](more.mapToGlobal(more.rect().bottomRight())))
        head.addWidget(more, 0, Qt.AlignTop)
        col.addLayout(head)

        if deleted:
            from .kit import Banner
            days = model.trash_days_left
            text = (f"Se borra del archivo dentro de {days} días. Mientras tanto sigue cifrada como el resto."
                    if days is not None and days > 0 else "Está en la papelera, cifrada como el resto.")
            col.addWidget(Banner("warning", "En la papelera.", text, actions=[
                Button("Restaurar", "banner", "history", on_click=cb["restore"]),
                Button("Borrar para siempre", "danger", on_click=cb["purge"]),
            ]))
        elif model.alert is not None:
            from .kit import Banner
            action = Button(model.alert.action, "banner", on_click=lambda: cb["alert"](model.alert.action_key))
            action.setProperty("tone", model.alert.tone)
            col.addWidget(Banner(model.alert.tone, f"{model.alert.short}.", model.alert.text, actions=[action]))

        # fields
        fields = QFrame()
        fields.setObjectName("card")
        fl = QVBoxLayout(fields)
        fl.setContentsMargins(0, 4, 0, 4)
        fl.setSpacing(0)
        rows: list[QWidget] = []
        user = getattr(view, "username", "") or ""
        if user or kind in ("login", "api_key"):
            copy_user = icon_button("copy", f"Copiar {USER_LABELS.get(kind, 'usuario').lower()} (Ctrl+B)",
                                    cb["copy_user"], 18)
            copy_user.setEnabled(bool(user) and not deleted)
            value = label(user or "—", "fieldValue", selectable=True)
            rows.append(_field_row(USER_LABELS.get(kind, "Usuario"), value, [copy_user]))
        if kind != "note":
            self.secret_lbl = label(MASK, "secret", selectable=False)
            self.secret_lbl.setAccessibleName(f"{SECRET_LABELS.get(kind, 'Contraseña')} oculta")
            secret_box = QHBoxLayout()
            secret_box.setSpacing(12)
            secret_box.addWidget(self.secret_lbl)
            self.hide_hint = QWidget()
            self.hide_hint.setObjectName("transparent")
            hh = QHBoxLayout(self.hide_hint)
            hh.setContentsMargins(0, 0, 0, 0)
            hh.setSpacing(4)
            hh.addWidget(icon_label("clock", P.TEXT_TERTIARY, 13))
            self.hide_hint_text = label("", "tertiary")
            hh.addWidget(self.hide_hint_text)
            self.hide_hint.hide()
            secret_box.addWidget(self.hide_hint)
            secret_box.addStretch(1)
            holder = QWidget()
            holder.setObjectName("transparent")
            holder.setLayout(secret_box)
            self.reveal_btn = Button("Revelar", "ghost", "eye", on_click=cb["reveal"])
            self.copy_btn = Button("Copiar", "secondary", "copy", on_click=cb["copy_secret"],
                                   tooltip="Copiar (Ctrl+C)")
            for b in (self.reveal_btn, self.copy_btn):
                b.setEnabled(not deleted)
            rows.append(_field_row(SECRET_LABELS.get(kind, "Contraseña"), holder, [self.reveal_btn, self.copy_btn]))
        else:
            self.secret_lbl = label(MASK, "secret")
            self.reveal_btn = Button("Revelar", "ghost", "eye", on_click=cb["reveal"])
            self.copy_btn = Button("Copiar", "secondary", "copy", on_click=cb["copy_secret"])
            self.reveal_btn.setEnabled(not deleted)
            self.copy_btn.setEnabled(not deleted)
            self.hide_hint = QWidget()
            self.hide_hint_text = label("", "tertiary")
            note_holder = QWidget()
            note_holder.setObjectName("transparent")
            nh = QVBoxLayout(note_holder)
            nh.setContentsMargins(0, 0, 0, 0)
            self.secret_lbl.setWordWrap(True)
            nh.addWidget(self.secret_lbl)
            rows.append(_field_row("Contenido", note_holder, [self.reveal_btn, self.copy_btn]))
        url = getattr(view, "url", "") or ""
        if url:
            open_btn = icon_button("external", "Abrir sitio en el navegador", cb["open_url"], 18)
            rows.append(_field_row("Sitio", label(host_of(url), "fieldValue", selectable=True), [open_btn]))
        if model.strength is not None and kind in ("login", "api_key"):
            level = int(getattr(model.strength, "level", 0))
            bits = int(round(getattr(model.strength, "bits", 0)))
            names = {0: "Muy débil", 1: "Débil", 2: "Aceptable", 3: "Fuerte", 4: "Muy fuerte"}
            tone = "success" if level >= 3 else ("warning" if level == 2 else "danger")
            badge = Badge(f"{names.get(level, '')} · {bits} bits", tone, "check" if tone == "success" else "warning")
            badge.setFixedHeight(26)
            wrap = QWidget()
            wrap.setObjectName("transparent")
            wl = QHBoxLayout(wrap)
            wl.setContentsMargins(0, 0, 0, 0)
            wl.addWidget(badge)
            wl.addStretch(1)
            rows.append(_field_row("Fuerza", wrap, []))
        for i, row in enumerate(rows):
            if i:
                fl.addWidget(hline())
            fl.addWidget(row)
        col.addWidget(fields)

        # 2FA
        self.code_lbl = QLabel("")
        self.ring = None
        if getattr(view, "has_totp", False) and not deleted:
            totp = QFrame()
            totp.setObjectName("card")
            t = QHBoxLayout(totp)
            t.setContentsMargins(24, 16, 16, 16)
            t.setSpacing(16)
            cap = label("Código 2FA", "fieldLabel")
            cap.setFixedWidth(160)
            t.addWidget(cap)
            self.code_lbl = label("", "code", selectable=True)
            self.code_lbl.setAccessibleName("Código 2FA actual")
            t.addWidget(self.code_lbl)
            self.ring = Ring(34, 3.0, 12)
            self.ring.setAccessibleName("Segundos hasta el siguiente código")
            t.addWidget(self.ring)
            self.code_hint = label("", "tertiary")
            t.addWidget(self.code_hint, 1)
            t.addWidget(Button("Copiar código", "secondary", "copy", on_click=cb["copy_code"], tooltip="Ctrl+T"))
            col.addWidget(totp)
        elif kind == "login" and not deleted:
            sug = QFrame()
            sug.setObjectName("cardDashed")
            s = QHBoxLayout(sug)
            s.setContentsMargins(24, 14, 16, 14)
            s.setSpacing(16)
            cap = label("Código 2FA", "fieldLabel")
            cap.setFixedWidth(160)
            s.addWidget(cap)
            s.addWidget(label("Si el sitio admite verificación en dos pasos, añádela: frena a quien tenga la "
                              "contraseña.", "secondary", wrap=True), 1)
            s.addWidget(Button("Añadir TOTP", "secondary", "add", on_click=cb["add_totp"]))
            col.addWidget(sug)

        # notes + tags
        notes = getattr(view, "notes", "") or ""
        tags = list(getattr(view, "tags", ()) or ())
        if (notes and kind != "note") or tags:
            pair = QHBoxLayout()
            pair.setSpacing(16)
            if notes and kind != "note":
                card = QFrame()
                card.setObjectName("card")
                c = QVBoxLayout(card)
                c.setContentsMargins(24, 16, 24, 18)
                c.setSpacing(8)
                c.addWidget(label("Notas", "fieldLabel"))
                c.addWidget(label(notes, "body", wrap=True, selectable=True))
                pair.addWidget(card, 3)
            if tags:
                card = QFrame()
                card.setObjectName("card")
                c = QVBoxLayout(card)
                c.setContentsMargins(24, 16, 24, 18)
                c.setSpacing(10)
                c.addWidget(label("Etiquetas", "fieldLabel"))
                flow = QHBoxLayout()
                flow.setSpacing(8)
                for tag in tags[:8]:
                    flow.addWidget(label(tag, "tag"))
                flow.addStretch(1)
                c.addLayout(flow)
                c.addStretch(1)
                pair.addWidget(card, 2)
            col.addLayout(pair)

        # history
        if model.history:
            card = QFrame()
            card.setObjectName("card")
            c = QVBoxLayout(card)
            c.setContentsMargins(24, 16, 24, 18)
            c.setSpacing(10)
            top = QHBoxLayout()
            top.addWidget(label("Historial", "fieldLabel"))
            top.addStretch(1)
            link = Button("Ver en la auditoría", "link", on_click=cb["audit"])
            top.addWidget(link)
            c.addLayout(top)
            for text, when in model.history[:6]:
                r = QHBoxLayout()
                r.setSpacing(10)
                dot = QLabel("•")
                dot.setStyleSheet(f"color: {P.TEXT_TERTIARY}; background: transparent;")
                r.addWidget(dot)
                r.addWidget(label(text, "body"), 1)
                r.addWidget(label(when, "secondary"))
                c.addLayout(r)
            col.addWidget(card)
        col.addStretch(1)
        self.scroll.setWidget(content)

    # live updates
    def set_revealed(self, secret: str | None, seconds_left: int | None = None) -> None:
        if secret is None:
            self.secret_lbl.setText(MASK)
            self.secret_lbl.setTextInteractionFlags(Qt.NoTextInteraction)
            if self.reveal_btn is not None:
                self.reveal_btn.set_label("Revelar")
                self.reveal_btn.set_icon_name("eye")
            if self.hide_hint is not None:
                self.hide_hint.hide()
            return
        self.secret_lbl.setText(secret)
        self.secret_lbl.setTextInteractionFlags(Qt.TextSelectableByMouse)
        if self.reveal_btn is not None:
            self.reveal_btn.set_label("Ocultar")
            self.reveal_btn.set_icon_name("eye-off")
        if self.hide_hint is not None and seconds_left:
            self.hide_hint_text.setText(f"Se oculta en {seconds_left} s")
            self.hide_hint.show()

    def set_code(self, code: str, remaining: int, period: int = 30) -> None:
        from .kit import group_code
        self.code_lbl.setText(group_code(code))
        if self.ring is not None:
            color = P.WARNING if remaining <= 5 else P.ACCENT
            self.ring.set_value(remaining / max(1, period), str(remaining), color)
            self.code_hint.setText("cambia en unos segundos" if remaining <= 5 else f"válido {remaining} s más")


def _field_row(caption: str, value: QWidget, actions: list[QWidget]) -> QWidget:
    row = QWidget()
    row.setObjectName("transparent")
    r = QHBoxLayout(row)
    r.setContentsMargins(24, 12, 12, 12)
    r.setSpacing(12)
    cap = label(caption, "fieldLabel")
    cap.setFixedWidth(160)
    r.addWidget(cap)
    r.addWidget(value, 1)
    for a in actions:
        r.addWidget(a)
    row.setMinimumHeight(56)
    return row


def compact_for(width: int) -> bool:
    return width < COMPACT_BELOW_W


__all__ = ["TopBar", "Sidebar", "ListPanel", "DetailPanel", "DetailModel", "RowAlert", "EntryRow",
           "NavItem", "HealthCard", "compact_for", "MASK", "Kbd"]
