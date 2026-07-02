"""Audit-ledger exporters for SIEM ingestion: JSON, CEF, and syslog.

Each takes the hash-chained audit blocks and renders them in a machine format a
SIEM (Splunk, ArcSight, QRadar, Sentinel…) can ingest. The hash + prev-hash
fields travel with each event, so a SIEM can attest the chain too.
"""
from __future__ import annotations

import json

_SEVERITY = {"init": 1, "add": 3, "remove": 6, "reveal": 4,
             "rotate": 6, "recovery-enroll": 5, "recover": 8}


def _sev(action: str) -> int:
    return _SEVERITY.get(action, 3)


class JsonAuditExporter:
    format = "json"

    def export(self, blocks) -> str:
        return json.dumps([
            {"index": b.index, "timestamp": b.timestamp, "action": b.action,
             "detail": b.detail, "prev_hash": b.prev_hash, "hash": b.hash}
            for b in blocks
        ], indent=2)


class CefAuditExporter:
    """ArcSight Common Event Format, one event per line."""

    format = "cef"

    def export(self, blocks) -> str:
        lines = []
        for b in blocks:
            ext = (f"end={b.timestamp} cn1Label=index cn1={b.index} "
                   f"cs1Label=blockHash cs1={b.hash} "
                   f"cs2Label=prevHash cs2={b.prev_hash} "
                   f"msg={b.detail}")
            lines.append(
                f"CEF:0|ferrovault|vault|1.0|{b.action}|{b.action}|{_sev(b.action)}|{ext}")
        return "\n".join(lines)


class SyslogAuditExporter:
    """RFC 5424-style structured lines (local0.info)."""

    format = "syslog"

    def export(self, blocks) -> str:
        lines = []
        for b in blocks:
            detail = b.detail.replace('"', "'")
            lines.append(
                f'<134>1 {b.timestamp} - ferrovault audit - - '
                f'[audit index="{b.index}" action="{b.action}" '
                f'detail="{detail}" hash="{b.hash}" prev="{b.prev_hash}"]')
        return "\n".join(lines)


_EXPORTERS = {"json": JsonAuditExporter, "cef": CefAuditExporter,
              "syslog": SyslogAuditExporter}


def build_exporter(fmt: str):
    try:
        return _EXPORTERS[fmt]()
    except KeyError as exc:
        raise ValueError(f"unknown export format: {fmt}") from exc
