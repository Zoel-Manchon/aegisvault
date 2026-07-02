"""Vault agent command dispatch + auto-lock behaviour."""
import os
import tempfile

import pytest

pytest.importorskip("cryptography")
from ferrovault.container import build_vault_service            # noqa: E402
from ferrovault.adapters.inbound.agent import VaultAgent        # noqa: E402


def _agent():
    d = tempfile.mkdtemp()
    svc = build_vault_service(os.path.join(d, "v.fv"))
    svc.init_vault("pw")
    s = svc.unlock("pw")
    s.add("github", "z", "s3cr3t", category="Dev")
    return VaultAgent(s, os.path.join(d, "a.sock"), timeout=1)


def test_agent_serves_and_locks():
    ag = _agent()
    assert "github" in ag._handle("LIST")
    assert ag._handle("GET github") == "s3cr3t"
    assert ag._handle("GET nope") == "not-found"
    assert ag._handle("LOCK") == "locked"
    assert ag._handle("GET github") == "locked"   # refuses after lock
