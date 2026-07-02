"""Secret injection: entries -> environment variables."""
import os
import tempfile

import pytest

pytest.importorskip("cryptography")
from ferrovault.container import build_vault_service  # noqa: E402


def test_secret_env_sanitises_names_and_prefixes():
    with tempfile.TemporaryDirectory() as d:
        svc = build_vault_service(os.path.join(d, "v.fv"))
        svc.init_vault("pw")
        svc.add_entry("pw", "prod db", "u", "dsn-1")
        svc.add_entry("pw", "stripe.key", "u", "sk_live_x")
        env = svc.secret_env("pw", prefix="FV_")
        assert env["FV_PROD_DB"] == "dsn-1"
        assert env["FV_STRIPE_KEY"] == "sk_live_x"
