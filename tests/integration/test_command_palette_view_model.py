from __future__ import annotations

from dataclasses import dataclass

from ferrovault.adapters.inbound.gui.view_models.command_palette import (
    DEFAULT_ACTIONS,
    build_command_index,
    fuzzy_score,
    search_commands,
)


@dataclass(frozen=True)
class Entry:
    name: str
    username: str = ""
    url: str = ""
    category: str = ""
    team_vault: str = "Personal"
    tags: tuple[str, ...] = ()
    deleted: bool = False


def test_fuzzy_score_matches_ordered_letters():
    assert fuzzy_score("bnc", "Binance production api key") > 0
    assert fuzzy_score("xyz", "Binance production api key") == 0


def test_command_palette_indexes_entries_and_actions():
    commands = build_command_index(
        [Entry("Binance prod", username="ops", url="https://binance.com", category="crypto")],
        DEFAULT_ACTIONS,
    )
    results = search_commands(commands, "binance")
    assert results[0].kind == "entry"
    assert results[0].payload == "Binance prod"


def test_command_palette_finds_zero_trust_actions():
    results = search_commands(DEFAULT_ACTIONS, "webauthn")
    assert results
    assert results[0].id == "action:passkey"
