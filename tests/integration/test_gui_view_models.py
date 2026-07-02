"""GUI view-models stay independent from Qt widgets."""
from dataclasses import dataclass

from ferrovault.adapters.inbound.gui.view_models.zero_trust import build_zero_trust_dashboard_model
from ferrovault.application.services.settings import VaultSettings


@dataclass
class _Verdict:
    ok: bool = True


@dataclass
class _Health:
    score: int = 92


@dataclass
class _Posture:
    role: str = "admin"
    trusted_device: bool = True
    rotation_overdue: int = 2
    twofa_coverage_percent: int = 75
    teams: tuple = ()


@dataclass
class _Finding:
    entry_name: str
    status: str
    age_days: int
    days_overdue: int = 0


class _Session:
    def verify_integrity(self):
        return _Verdict(), "fingerprint-value", "head-hash-value"

    def health_report(self):
        return _Health()

    def enterprise_posture(self, identity):
        assert identity.role == "admin"
        return _Posture()

    def rotation_report(self):
        return (_Finding("prod-db", "overdue", 123, 33),)


@dataclass
class _Entry:
    deleted: bool = False
    active_share_count: int = 2


def test_zero_trust_view_model_normalizes_dashboard_state():
    settings = VaultSettings(
        enterprise_role="admin",
        local_device_id="laptop-1",
        trusted_device_ids=("laptop-1",),
        policy_enforcement_enabled=True,
    )

    model = build_zero_trust_dashboard_model(_Session(), settings, [_Entry()])

    assert model.score == "87"
    assert model.audit_state == "Verified"
    assert model.role == "Admin"
    assert model.device == "Trusted"
    assert model.grants == 2
    assert model.rotation_lines[0].startswith("prod-db: overdue")

from ferrovault.adapters.inbound.gui.view_models.vault_list import (
    ALL_CATEGORIES,
    VaultListViewModel,
)


@dataclass
class _ListEntry:
    name: str
    username: str = ""
    url: str = ""
    tags: tuple = ()
    category: str = ""
    has_totp: bool = False
    favorite: bool = False
    deleted: bool = False
    shared_with: tuple = ()
    active_share_count: int = 0
    revoked_share_count: int = 0


def test_vault_list_view_model_filters_sorts_and_pages_without_qt():
    entries = [
        _ListEntry("z-prod", "root", "https://binance.com", category="Crypto", has_totp=True, active_share_count=1),
        _ListEntry("alpha", "ops", "https://github.com", category="Dev", favorite=True),
        _ListEntry("beta", "trash", category="Dev", deleted=True),
        _ListEntry("gamma", "auditor", category="Crypto", revoked_share_count=1),
    ]
    vm = VaultListViewModel(page_size=2)

    assert vm.categories(entries) == (ALL_CATEGORIES, "Crypto", "Dev")
    overview = vm.overview(entries)
    assert overview.total == 3
    assert overview.favorites == 1
    assert overview.twofa == 1
    assert overview.shared == 1
    assert overview.categories[0].name == "Crypto"
    assert overview.categories[0].count == 2

    vm.set_category("Crypto")
    result = vm.page(entries)
    assert [e.name for e in result.entries] == ["z-prod", "gamma"]
    assert result.count_label == "1–2 of 2"

    vm.toggle_sort()
    result = vm.page(entries)
    assert [e.name for e in result.entries] == ["gamma", "z-prod"]

    vm.set_section("Shared")
    result = vm.page(entries)
    assert [e.name for e in result.entries] == ["gamma", "z-prod"]

    vm.set_category(ALL_CATEGORIES)
    vm.set_section("Trash")
    result = vm.page(entries)
    assert [e.name for e in result.entries] == ["beta"]


def test_vault_list_view_model_keeps_page_bounds_and_search_state():
    entries = [_ListEntry(f"entry-{idx}", username="ops") for idx in range(5)]
    vm = VaultListViewModel(page_size=2)

    vm.set_page(1)
    assert [e.name for e in vm.page(entries).entries] == ["entry-2", "entry-3"]

    vm.set_query("entry-4")
    result = vm.page(entries)
    assert result.state.page == 0
    assert [e.name for e in result.entries] == ["entry-4"]
    assert result.count_label == "1–1 of 1"

    vm.set_page(99)
    result = vm.page(entries)
    assert result.state.page == 0

from ferrovault.adapters.inbound.gui.view_models.dashboard import (
    build_vault_dashboard_model,
    grid_rows,
)


def test_vault_dashboard_model_maps_overview_metrics_and_categories():
    entries = [
        _ListEntry("binance", "trader", "https://binance.com", category="Crypto", has_totp=True, active_share_count=1),
        _ListEntry("github", "zoel", "https://github.com", category="Dev", favorite=True),
    ]
    overview = VaultListViewModel().overview(entries)

    model = build_vault_dashboard_model(overview)

    assert [m.value for m in model.metrics] == ["2", "1", "1", "1"]
    assert model.categories[0].name in {"Crypto", "Dev"}
    assert {c.top_url for c in model.categories} == {"https://binance.com", "https://github.com"}


def test_dashboard_grid_rows_are_stable_and_column_bound():
    rows = grid_rows(("a", "b", "c"), columns=2)

    assert rows == ((0, 0, "a"), (0, 1, "b"), (1, 0, "c"))
