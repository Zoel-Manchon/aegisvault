"""SIEM streaming service and durable sinks."""
from __future__ import annotations

import json
import socket
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(frozen=True)
class SiemEvent:
    vendor: str
    product: str
    event_type: str
    timestamp: str
    severity: int
    message: str
    index: int
    hash: str
    prev_hash: str


_SEVERITY = {
    "init": 1,
    "add": 3,
    "import": 4,
    "share": 5,
    "unshare": 5,
    "trash": 5,
    "purge": 8,
    "rotate": 6,
    "recovery-enroll": 5,
    "recover": 8,
    "policy-deny": 6,
    "break-glass": 9,
}


def normalize_blocks(blocks) -> tuple[SiemEvent, ...]:
    events = []
    for b in blocks:
        events.append(SiemEvent(
            vendor="ferrovault",
            product="secrets-vault",
            event_type=b.action,
            timestamp=b.timestamp,
            severity=_SEVERITY.get(b.action, 3),
            message=b.detail,
            index=b.index,
            hash=b.hash,
            prev_hash=b.prev_hash,
        ))
    return tuple(events)


class MemorySiemSink:
    def __init__(self):
        self.events: list[SiemEvent] = []

    def write(self, event: SiemEvent) -> None:
        self.events.append(event)


class JsonlFileSiemSink:
    """Append one normalized SIEM event per line."""

    def __init__(self, path: str | Path):
        self.path = Path(path)

    def write(self, event: SiemEvent) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(asdict(event), sort_keys=True) + "\n")


class UdpSyslogSiemSink:
    """Best-effort UDP syslog sink for lab integrations."""

    def __init__(self, host: str = "127.0.0.1", port: int = 514):
        self.host = host
        self.port = int(port)

    def write(self, event: SiemEvent) -> None:
        message = (
            f'<134>1 {event.timestamp} - ferrovault audit - - '
            f'[audit index="{event.index}" action="{event.event_type}" '
            f'hash="{event.hash}" prev="{event.prev_hash}"] {event.message}'
        )
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.sendto(message.encode("utf-8"), (self.host, self.port))


class SiemStreamer:
    def __init__(self, sink):
        self.sink = sink

    def stream(self, blocks) -> int:
        count = 0
        for event in normalize_blocks(blocks):
            self.sink.write(event)
            count += 1
        return count
