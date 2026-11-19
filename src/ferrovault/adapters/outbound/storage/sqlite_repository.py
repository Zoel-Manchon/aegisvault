"""SQLite-backed VaultRepository.

Same port as FileVaultRepository, but persists the encrypted artifact in a
SQLite database (single-writer, transactional, corruption-resistant). The
ciphertext is stored as-is - the database never sees plaintext, so the
zero-knowledge property is identical to the file backend. Selected by the
composition root when the vault path ends in `.db` / `.sqlite`.

This is also the stepping stone to a server-mode PostgreSQL adapter: the port
is identical, only the SQL driver changes.
"""
from __future__ import annotations

import base64
import json
import sqlite3
from contextlib import closing

from ....application.services.dto import EncryptedVault

_SCHEMA = """
CREATE TABLE IF NOT EXISTS vault (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    header TEXT NOT NULL,
    nonce  BLOB NOT NULL,
    ciphertext BLOB NOT NULL,
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);
"""


class SqliteVaultRepository:
    def __init__(self, path: str, backup_dir: str | None = None, keep: int = 10):
        self._path = path
        self._backup_dir = backup_dir
        self._keep = max(1, int(keep))

    @property
    def path(self) -> str:
        return self._path

    def snapshot(self, label: str = "manual") -> str | None:
        """Consistent copy through SQLite's online backup API."""
        import os
        import time
        from pathlib import Path
        if not os.path.exists(self._path):
            return None
        src = Path(self._path)
        folder = Path(self._backup_dir) if self._backup_dir else src.parent / f"{src.stem}-copias"
        folder.mkdir(parents=True, exist_ok=True)
        safe = "".join(c if c.isalnum() or c in "-_" else "-" for c in label)[:32] or "copia"
        stamp = time.strftime('%Y%m%d-%H%M%S')
        dest = folder / f"{src.stem}-{stamp}-{safe}{src.suffix}"
        n = 1
        while dest.exists():                      # never back up over an earlier snapshot
            dest = folder / f"{src.stem}-{stamp}-{safe}-{n}{src.suffix}"
            n += 1
        with closing(sqlite3.connect(self._path)) as source, closing(sqlite3.connect(dest)) as target:
            source.backup(target)
        for old in sorted(folder.glob(f"{src.stem}-*{src.suffix}"),
                          key=lambda p: (p.stat().st_mtime_ns, p.name), reverse=True)[self._keep:]:
            try:
                old.unlink()
            except OSError:
                pass
        return str(dest)

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._path)
        conn.execute(_SCHEMA)
        return conn

    def exists(self) -> bool:
        try:
            with closing(self._conn()) as conn, conn:
                row = conn.execute("SELECT 1 FROM vault WHERE id = 1").fetchone()
            return row is not None
        except sqlite3.Error:
            return False

    def load(self) -> EncryptedVault:
        with closing(self._conn()) as conn, conn:
            row = conn.execute(
                "SELECT header, nonce, ciphertext FROM vault WHERE id = 1").fetchone()
        if row is None:
            raise FileNotFoundError(f"no vault stored in {self._path}")
        header, nonce, ciphertext = row
        return EncryptedVault(header=json.loads(header),
                              nonce=bytes(nonce), ciphertext=bytes(ciphertext))

    def save(self, artifact: EncryptedVault) -> None:
        with closing(self._conn()) as conn, conn:
            conn.execute(
                "INSERT INTO vault (id, header, nonce, ciphertext, updated_at) "
                "VALUES (1, ?, ?, ?, datetime('now')) "
                "ON CONFLICT(id) DO UPDATE SET header=excluded.header, "
                "nonce=excluded.nonce, ciphertext=excluded.ciphertext, "
                "updated_at=excluded.updated_at",
                (json.dumps(artifact.header), artifact.nonce, artifact.ciphertext))
