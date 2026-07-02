"""Qt-independent view-model for vault list filtering and paging."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping

DEFAULT_PAGE_SIZE = 8
ALL_CATEGORIES = "All categories"
VALID_SORTS = {"recent", "name"}
LIST_SECTIONS = {"Vault", "Categories", "Favorites", "Shared", "Trash", "Zero Trust"}


@dataclass(frozen=True)
class CategorySummary:
    """Aggregated category metadata for dashboard/category cards."""

    name: str
    count: int = 0
    favorites: int = 0
    twofa: int = 0
    shared: int = 0
    top_url: str = ""

    def to_card_data(self) -> dict[str, object]:
        return {
            "count": self.count,
            "favorites": self.favorites,
            "twofa": self.twofa,
            "shared": self.shared,
            "top_url": self.top_url,
        }


@dataclass(frozen=True)
class VaultOverview:
    """Small metric row shown above the collection/category cards."""

    total: int
    favorites: int
    twofa: int
    shared: int
    categories: tuple[CategorySummary, ...]


@dataclass(frozen=True)
class VaultListState:
    """User-facing state for the current vault-list screen."""

    section: str = "Vault"
    category: str = ALL_CATEGORIES
    sort: str = "recent"
    query: str = ""
    page: int = 0
    selected_name: str | None = None

    def normalized(self) -> "VaultListState":
        section = self.section if self.section in LIST_SECTIONS else "Vault"
        category = self.category or ALL_CATEGORIES
        sort = self.sort if self.sort in VALID_SORTS else "recent"
        return VaultListState(
            section=section,
            category=category,
            sort=sort,
            query=self.query or "",
            page=max(0, int(self.page or 0)),
            selected_name=self.selected_name,
        )

    def with_section(self, section: str) -> "VaultListState":
        section = section if section in LIST_SECTIONS else "Vault"
        # Dashboards are not category-filtered lists; reset selection to avoid
        # stale detail panes when moving from an entry section to a dashboard.
        if section in {"Zero Trust", "Categories"}:
            return VaultListState(section=section, selected_name=None)
        return VaultListState(
            section=section,
            category=self.category,
            sort=self.sort,
            query=self.query,
            page=0,
            selected_name=self.selected_name,
        ).normalized()

    def with_category(self, category: str) -> "VaultListState":
        return VaultListState(
            section=self.section,
            category=category or ALL_CATEGORIES,
            sort=self.sort,
            query=self.query,
            page=0,
            selected_name=self.selected_name,
        ).normalized()

    def with_query(self, query: str) -> "VaultListState":
        return VaultListState(
            section=self.section,
            category=self.category,
            sort=self.sort,
            query=query or "",
            page=0,
            selected_name=self.selected_name,
        ).normalized()

    def with_sort(self, sort: str) -> "VaultListState":
        return VaultListState(
            section=self.section,
            category=self.category,
            sort=sort if sort in VALID_SORTS else "recent",
            query=self.query,
            page=0,
            selected_name=self.selected_name,
        ).normalized()

    def toggled_sort(self) -> "VaultListState":
        return self.with_sort("name" if self.sort == "recent" else "recent")

    def with_page(self, page: int) -> "VaultListState":
        return VaultListState(
            section=self.section,
            category=self.category,
            sort=self.sort,
            query=self.query,
            page=page,
            selected_name=self.selected_name,
        ).normalized()

    def with_selection(self, selected_name: str | None) -> "VaultListState":
        return VaultListState(
            section=self.section,
            category=self.category,
            sort=self.sort,
            query=self.query,
            page=self.page,
            selected_name=selected_name,
        ).normalized()

    def reset_filters(self) -> "VaultListState":
        return VaultListState(section=self.section, selected_name=self.selected_name)


@dataclass(frozen=True)
class VaultListResult:
    """Filtered/paginated list output consumed by Qt widgets."""

    state: VaultListState
    entries: tuple[Any, ...]
    matched_count: int
    total_pages: int
    count_label: str

    @property
    def selected_name(self) -> str | None:
        return self.state.selected_name


class VaultListViewModel:
    """Pure list/query/category state for the main vault workspace.

    This object intentionally has no PySide dependency. It can be tested without
    a running QApplication and lets MainWindow focus on rendering instead of
    owning filtering, sorting, page bounds, and category aggregation.
    """

    def __init__(self, *, page_size: int = DEFAULT_PAGE_SIZE, state: VaultListState | None = None):
        self.page_size = max(1, int(page_size))
        self.state = (state or VaultListState()).normalized()

    # ---- state mutations -------------------------------------------------
    def set_section(self, section: str) -> VaultListState:
        self.state = self.state.with_section(section)
        return self.state

    def set_category(self, category: str) -> VaultListState:
        self.state = self.state.with_category(category)
        return self.state

    def filter_category_from_dashboard(self, category: str) -> VaultListState:
        self.state = VaultListState(section="Vault", category=category or ALL_CATEGORIES).normalized()
        return self.state

    def set_query(self, query: str) -> VaultListState:
        self.state = self.state.with_query(query)
        return self.state

    def toggle_sort(self) -> VaultListState:
        self.state = self.state.toggled_sort()
        return self.state

    def reset_filters(self) -> VaultListState:
        self.state = self.state.reset_filters()
        return self.state

    def set_page(self, page: int) -> VaultListState:
        self.state = self.state.with_page(page)
        return self.state

    def set_selection(self, selected_name: str | None) -> VaultListState:
        self.state = self.state.with_selection(selected_name)
        return self.state

    # ---- projections -----------------------------------------------------
    def categories(self, entries: Iterable[Any]) -> tuple[str, ...]:
        cats = sorted({str(getattr(v, "category", "")) for v in entries if str(getattr(v, "category", ""))})
        return (ALL_CATEGORIES, *cats)

    def overview(self, entries: Iterable[Any]) -> VaultOverview:
        active = [v for v in entries if not _deleted(v)]
        summaries: dict[str, dict[str, object]] = {}
        for view in active:
            category = str(getattr(view, "category", "") or "")
            if not category:
                continue
            item = summaries.setdefault(
                category,
                {"count": 0, "favorites": 0, "twofa": 0, "shared": 0, "top_url": ""},
            )
            item["count"] = int(item["count"]) + 1
            if not item["top_url"] and getattr(view, "url", ""):
                item["top_url"] = str(getattr(view, "url", ""))
            if _favorite(view):
                item["favorites"] = int(item["favorites"]) + 1
            if _has_totp(view):
                item["twofa"] = int(item["twofa"]) + 1
            if _shared(view):
                item["shared"] = int(item["shared"]) + 1

        categories = tuple(
            CategorySummary(
                name=name,
                count=int(data["count"]),
                favorites=int(data["favorites"]),
                twofa=int(data["twofa"]),
                shared=int(data["shared"]),
                top_url=str(data["top_url"]),
            )
            for name, data in sorted(summaries.items(), key=lambda x: (-int(x[1]["count"]), x[0].lower()))
        )
        return VaultOverview(
            total=len(active),
            favorites=sum(1 for v in active if _favorite(v)),
            twofa=sum(1 for v in active if _has_totp(v)),
            shared=sum(1 for v in active if _shared(v)),
            categories=categories,
        )

    def page(self, entries: Iterable[Any]) -> VaultListResult:
        filtered = self._filter(entries)
        pages = max(1, (len(filtered) + self.page_size - 1) // self.page_size)
        page = max(0, min(self.state.page, pages - 1))
        if page != self.state.page:
            self.state = self.state.with_page(page)
        start_index = page * self.page_size
        page_items = tuple(filtered[start_index:start_index + self.page_size])
        return VaultListResult(
            state=self.state,
            entries=page_items,
            matched_count=len(filtered),
            total_pages=pages,
            count_label=self._count_label(len(filtered), len(page_items), page),
        )

    def _filter(self, entries: Iterable[Any]) -> list[Any]:
        state = self.state.normalized()
        views = list(entries)
        if state.section == "Favorites":
            views = [v for v in views if _favorite(v) and not _deleted(v)]
        elif state.section == "Shared":
            views = [v for v in views if _shared_or_historical(v) and not _deleted(v)]
        elif state.section == "Trash":
            views = [v for v in views if _deleted(v)]
        elif state.section == "Zero Trust":
            views = []
        else:
            views = [v for v in views if not _deleted(v)]

        if state.category != ALL_CATEGORIES:
            target = state.category.lower()
            views = [v for v in views if str(getattr(v, "category", "")).lower() == target]

        if state.sort == "name":
            views.sort(key=lambda v: str(getattr(v, "name", "")).lower())

        query = state.query.lower().strip()
        if query:
            views = [v for v in views if query in _search_text(v)]
        return views

    def _count_label(self, matched_count: int, page_count: int, page: int) -> str:
        if self.state.section == "Zero Trust":
            return "Zero Trust panel"
        if matched_count == 0:
            return "No entries yet"
        start = page * self.page_size + 1
        return f"{start}–{start + page_count - 1} of {matched_count}"


def _deleted(view: Any) -> bool:
    return bool(getattr(view, "deleted", False))


def _favorite(view: Any) -> bool:
    return bool(getattr(view, "favorite", False))


def _has_totp(view: Any) -> bool:
    return bool(getattr(view, "has_totp", False))


def _shared(view: Any) -> bool:
    return bool(getattr(view, "shared_with", ()) or getattr(view, "active_share_count", 0))


def _shared_or_historical(view: Any) -> bool:
    return bool(_shared(view) or getattr(view, "revoked_share_count", 0))


def _search_text(view: Any) -> str:
    tags = getattr(view, "tags", ()) or ()
    return f"{getattr(view, 'name', '')} {getattr(view, 'username', '')} {getattr(view, 'url', '')} {' '.join(map(str, tags))}".lower()
