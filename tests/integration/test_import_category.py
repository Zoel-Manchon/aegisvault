"""Import from other managers, first-class category, and share marking."""
import os
import tempfile

import pytest

from ferrovault.adapters.outbound.importers.parsers import parse

pytest.importorskip("cryptography")
from ferrovault.container import build_vault_service  # noqa: E402
from ferrovault.adapters.outbound.sharing.sealed_box import generate_keypair  # noqa: E402


def test_bitwarden_and_csv_parse():
    bw = ('{"folders":[{"id":"f1","name":"Work"}],'
          '"items":[{"name":"GitHub","folderId":"f1",'
          '"login":{"username":"z","password":"p","uris":[{"uri":"https://gh.com"}]}}]}')
    recs = parse("bitwarden", bw)
    assert recs[0]["name"] == "GitHub" and recs[0]["category"] == "Work"
    csv_recs = parse("csv", "Title,Username,Password,Group\nGmail,z,secret,Email")
    assert csv_recs[0]["category"] == "Email"


def test_import_entries_and_category_persist():
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "v.fv")
        svc = build_vault_service(path)
        svc.init_vault("pw")
        records = [{"name": "GitHub", "username": "z", "secret": "p",
                    "category": "Work", "url": "https://gh.com"},
                   {"name": "GitHub", "username": "dup", "secret": "x"}]  # duplicate
        added, skipped = svc.import_entries("pw", records)
        assert (added, skipped) == (1, 1)
        # category survives a fresh open (round-trips through serialization)
        views = build_vault_service(path).list_entries("pw")
        assert views[0].category == "Work"


def test_share_marks_entry_shared():
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "v.fv")
        svc = build_vault_service(path)
        svc.init_vault("pw")
        svc.add_entry("pw", "db", "svc", "dsn", category="Infra")
        _priv, pub = generate_keypair()
        svc.share_secret("pw", "db", pub)
        view = [v for v in svc.list_entries("pw") if v.name == "db"][0]
        assert view.shared_with and view.shared_with[0] == pub[:12]
