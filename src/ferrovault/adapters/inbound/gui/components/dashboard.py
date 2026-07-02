"""Reusable dashboard renderers for the main desktop detail canvas."""
from __future__ import annotations

from collections.abc import Callable, Iterable
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget

from .cards import CategoryCard, MetricTile
from .primitives import EmptyHint, FeatureGrid, caption, clear_layout
from .zero_trust import ZeroTrustDashboard
from ..view_models.dashboard import build_vault_dashboard_model


class DashboardRenderer:
    """Render dashboard widgets into the right-side feature layout.

    MainWindow should decide *when* to render.  This class owns *how* dashboards
    are composed visually so layout changes do not keep bloating MainWindow.
    """

    def __init__(
        self,
        layout,
        *,
        on_category_selected: Callable[[str], None],
        zero_trust_actions: Iterable[tuple[str, str, str, Callable]],
        on_audit_export: Callable[[str], None],
    ):
        self._layout = layout
        self._on_category_selected = on_category_selected
        self._zero_trust_actions = tuple(zero_trust_actions)
        self._on_audit_export = on_audit_export

    def clear(self) -> None:
        clear_layout(self._layout)

    def render_vault_overview(self, overview: Any) -> None:
        self.clear()
        model = build_vault_dashboard_model(overview)

        metrics = FeatureGrid(columns=2)
        metrics.add_items(MetricTile(metric.label, metric.value, metric.helper, tone=metric.tone) for metric in model.metrics)
        self._layout.addWidget(metrics)

        self._layout.addWidget(caption("COLLECTIONS", align=Qt.AlignCenter))

        if not model.categories:
            self._layout.addWidget(EmptyHint(model.empty_title, model.empty_body))
            return

        categories = FeatureGrid(columns=2)
        categories.add_items(self._category_card(category) for category in model.categories)
        self._layout.addWidget(categories)

    def render_zero_trust(self, model) -> None:
        self.clear()
        dashboard = ZeroTrustDashboard(
            score=model.score,
            audit_state=model.audit_state,
            audit_ok=model.audit_ok,
            role=model.role,
            device=model.device,
            device_ok=model.device_ok,
            overdue=model.overdue,
            twofa=model.twofa,
            policy_state=model.policy_state,
            policy_enforced=model.policy_enforced,
            grants=model.grants,
            pending_requests=model.pending_requests,
            actions=self._zero_trust_actions,
            team_lines=model.team_lines,
            rotation_lines=model.rotation_lines,
            fingerprint=model.fingerprint,
            head_hash=model.head_hash,
            on_export=self._on_audit_export,
        )
        self._layout.addWidget(dashboard)

    def _category_card(self, category) -> QWidget:
        card = CategoryCard(
            category.name,
            category.count,
            category.favorites,
            category.twofa,
            category.shared,
            category.top_url,
        )
        card.clicked.connect(lambda _=False, name=category.name: self._on_category_selected(name))
        return card
