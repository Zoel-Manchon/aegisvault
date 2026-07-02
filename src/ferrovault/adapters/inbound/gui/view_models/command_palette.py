"""Qt-free command palette model and fuzzy search helpers.

The GUI can render these commands with Qt Widgets today and QML later.  Keeping
matching and command construction outside Qt makes the palette fast, testable,
and reusable by the future Tauri/QML frontend.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable


@dataclass(frozen=True)
class PaletteCommand:
    id: str
    title: str
    subtitle: str = ""
    kind: str = "action"  # action | entry | section
    payload: Any = None
    keywords: tuple[str, ...] = ()

    @property
    def searchable(self) -> str:
        return " ".join((self.title, self.subtitle, self.kind, *self.keywords)).lower()


def fuzzy_score(query: str, text: str) -> int:
    """Return a small positive score when *query* fuzzily matches *text*.

    This intentionally avoids external dependencies.  It rewards exact/prefix
    matches, then falls back to ordered-character matching similar to command
    palettes.  A score of 0 means no match.
    """
    q = "".join(query.lower().split())
    t = text.lower()
    compact = "".join(t.split())
    if not q:
        return 1
    if q in compact:
        return 200 + max(0, 50 - compact.index(q))
    words = [w for w in t.replace("/", " ").replace("-", " ").split() if w]
    if any(w.startswith(q) for w in words):
        return 170

    pos = -1
    gaps = 0
    matched = 0
    for ch in q:
        new_pos = compact.find(ch, pos + 1)
        if new_pos == -1:
            return 0
        if pos >= 0:
            gaps += max(0, new_pos - pos - 1)
        pos = new_pos
        matched += 1
    return max(1, 120 + matched * 4 - gaps)


def build_command_index(entries: Iterable[Any], actions: Iterable[PaletteCommand]) -> tuple[PaletteCommand, ...]:
    commands: list[PaletteCommand] = list(actions)
    for entry in entries:
        if getattr(entry, "deleted", False):
            continue
        commands.append(
            PaletteCommand(
                id=f"entry:{entry.name}",
                title=entry.name,
                subtitle=" · ".join(x for x in (
                    getattr(entry, "username", ""),
                    getattr(entry, "category", "") or getattr(entry, "team_vault", ""),
                    getattr(entry, "url", ""),
                ) if x),
                kind="entry",
                payload=entry.name,
                keywords=tuple(getattr(entry, "tags", ()) or ()),
            )
        )
    return tuple(commands)


def search_commands(commands: Iterable[PaletteCommand], query: str, *, limit: int = 12) -> tuple[PaletteCommand, ...]:
    scored: list[tuple[int, str, PaletteCommand]] = []
    for command in commands:
        score = fuzzy_score(query, command.searchable)
        if score:
            # Actions before entries on tie, then stable title ordering.
            kind_bias = 15 if command.kind == "action" else 0
            scored.append((score + kind_bias, command.title.lower(), command))
    scored.sort(key=lambda item: (-item[0], item[1]))
    return tuple(command for _score, _title, command in scored[:limit])


DEFAULT_ACTIONS: tuple[PaletteCommand, ...] = (
    PaletteCommand("action:add", "Add secret", "Create a new credential", keywords=("new", "password")),
    PaletteCommand("action:sharing", "Open Sharing Center", "Create, list, receive, revoke grants", keywords=("grant", "share")),
    PaletteCommand("action:zero-trust", "Zero Trust dashboard", "Policy, identity, device, audit posture", keywords=("zt", "security")),
    PaletteCommand("action:siem", "Live audit stream", "Real-time SIEM activity feed", keywords=("audit", "events")),
    PaletteCommand("action:policy", "Policy Pack", "Edit local Zero Trust deny rules", keywords=("rules", "deny")),
    PaletteCommand("action:directory", "Directory", "Users, public keys, trusted devices", keywords=("users", "devices", "keys")),
    PaletteCommand("action:sync", "Sync Gateway", "Encrypted sync delivery preview", keywords=("bundle", "gateway")),
    PaletteCommand("action:access", "Access requests", "Just-in-time access approvals", keywords=("jit", "approve")),
    PaletteCommand("action:agent", "Browser autofill agent", "Local socket bridge for extension/autofill", keywords=("browser", "extension", "autofill")),
    PaletteCommand("action:passkey", "Passkey unlock", "Desktop biometric/WebAuthn foundation", keywords=("biometric", "webauthn", "yubikey")),
    PaletteCommand("action:health", "Health report", "Weak, reused, 2FA, rotation review", keywords=("score", "security")),
    PaletteCommand("action:settings", "Settings", "Security, identity, policy defaults", keywords=("preferences", "config")),
    PaletteCommand("action:guide", "Quick start guide", "How to use the vault safely", keywords=("help", "tutorial", "onboarding")),
)
