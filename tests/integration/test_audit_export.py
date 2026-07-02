"""Audit-ledger SIEM exporters."""
import json

from ferrovault.adapters.outbound.audit_export.exporters import build_exporter
from ferrovault.domain.model.audit import AuditLedger


def _ledger():
    led = AuditLedger()
    led.append("init", "vault created", "2026-01-01T00:00:00+00:00")
    led.append("add", "github", "2026-01-01T00:01:00+00:00")
    return led


def test_json_export_roundtrips():
    out = build_exporter("json").export(_ledger().blocks)
    data = json.loads(out)
    assert [b["action"] for b in data] == ["init", "add"]
    assert all("hash" in b and "prev_hash" in b for b in data)


def test_cef_export_shape():
    out = build_exporter("cef").export(_ledger().blocks)
    lines = out.splitlines()
    assert lines[0].startswith("CEF:0|ferrovault|vault|1.0|init|")
    assert "cs1Label=blockHash" in lines[1]


def test_syslog_export_shape():
    out = build_exporter("syslog").export(_ledger().blocks)
    assert out.splitlines()[0].startswith("<134>1 ")
    assert 'action="add"' in out


def test_unknown_format_rejected():
    import pytest
    with pytest.raises(ValueError):
        build_exporter("xml")
