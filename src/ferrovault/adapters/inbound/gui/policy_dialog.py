"""Editable GUI policy-pack rules."""
from __future__ import annotations

from PySide6.QtWidgets import QDialog, QMessageBox, QVBoxLayout

from ....application.services.policy_pack import PolicyPack, default_policy_rules
from ....application.services.settings import VaultSettings
from .components.dialogs import DialogHero
from .policy_sections import PolicyRuleFooter, PolicyRuleForm, PolicyRuleTable


class PolicyPackDialog(QDialog):
    def __init__(self, settings_store, settings: VaultSettings, parent=None):
        super().__init__(parent)
        self._settings_store = settings_store
        self._settings = settings.normalized()
        self._rules = list(PolicyPack.from_iterable(self._settings.policy_rules).rules)
        self.setWindowTitle("Zero Trust policy-pack editor")
        self.setMinimumSize(960, 640)
        self.resize(1100, 720)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(22, 20, 22, 18)
        outer.setSpacing(14)
        outer.addWidget(DialogHero(
            "Policy-pack editor",
            "Create deny rules for specific actions, sensitivity levels, team vaults, categories, MFA state, and trusted-device state. No code execution, only deterministic Zero Trust rules.",
        ))

        self.table = PolicyRuleTable()
        outer.addWidget(self.table, 1)

        self.form = PolicyRuleForm()
        outer.addWidget(self.form)

        self.footer = PolicyRuleFooter()
        self.footer.add_button.clicked.connect(self.add_rule)
        self.footer.load_button.clicked.connect(self.load_selected)
        self.footer.remove_button.clicked.connect(self.remove_selected)
        self.footer.reset_button.clicked.connect(self.restore_defaults)
        self.footer.save_button.clicked.connect(self.save)
        self.footer.close_button.clicked.connect(self.accept)
        outer.addWidget(self.footer)
        self.refresh()

    @property
    def settings(self) -> VaultSettings:
        return self._settings

    def refresh(self):
        self.table.set_rules(self._rules)

    def add_rule(self):
        rule = self.form.rule()
        self._rules = [r for r in self._rules if r.rule_id != rule.rule_id] + [rule]
        self.refresh()

    def load_selected(self):
        row = self.table.currentRow()
        if row < 0 or row >= len(self._rules):
            return
        self.form.load(self._rules[row])

    def remove_selected(self):
        row = self.table.currentRow()
        if row < 0 or row >= len(self._rules):
            return
        del self._rules[row]
        self.refresh()

    def restore_defaults(self):
        if QMessageBox.question(self, "Restore starter pack?", "Replace current rules with the starter Zero Trust policy pack?") != QMessageBox.Yes:
            return
        self._rules = list(PolicyPack.from_iterable(default_policy_rules()).rules)
        self.refresh()

    def save(self):
        self._settings = VaultSettings(**{**self._settings.to_dict(), "policy_rules": tuple(r.to_dict() for r in self._rules)}).normalized()
        self._settings_store.save(self._settings)
        QMessageBox.information(self, "Policy pack saved", "Zero Trust policy-pack rules were saved locally.")
