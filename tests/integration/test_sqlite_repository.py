"""SQLite storage adapter behind the same VaultRepository port."""
import os
import tempfile

import pytest

pytest.importorskip("cryptography")
from ferrovault.container import build_vault_service  # noqa: E402


def test_sqlite_backend_roundtrip_and_rotation():
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "vault.db")
        svc = build_vault_service(path)
        assert type(svc._repo).__name__ == "SqliteVaultRepository"
        svc.init_vault("pw")
        svc.add_entry("pw", "github", "z", "s3cr3t", category="Dev")
        assert build_vault_service(path).get_secret("pw", "github") == "s3cr3t"
        svc.rotate("pw", "pw2")
        assert build_vault_service(path).get_secret("pw2", "github") == "s3cr3t"
