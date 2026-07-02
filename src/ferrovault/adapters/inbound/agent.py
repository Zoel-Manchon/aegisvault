"""Vault agent: hold an unlocked session in memory and serve secrets over a
Unix socket, auto-locking after an idle timeout (ssh-agent style).

Inbound adapter. Commands (newline-terminated): LIST, GET <name>, CODE <name>,
LOCK. The private key material never leaves the process; clients get only the
requested secret. After `timeout` idle seconds the session is locked and the
socket removed.
"""
from __future__ import annotations

import os
import socket
import tempfile

DEFAULT_SOCKET = os.path.join(
    os.environ.get("XDG_RUNTIME_DIR", tempfile.gettempdir()), "ferrovault-agent.sock")


class VaultAgent:
    def __init__(self, session, socket_path=None, timeout=300):
        self._session = session
        self._path = socket_path or DEFAULT_SOCKET
        self._timeout = timeout
        self._locked = False

    def _handle(self, line: str) -> str:
        parts = line.strip().split(" ", 1)
        cmd = parts[0].upper() if parts and parts[0] else ""
        arg = parts[1].strip() if len(parts) > 1 else ""
        if self._locked:
            return "locked"
        if cmd == "LIST":
            return "\n".join(v.name for v in self._session.entries(include_deleted=False))
        if cmd == "GET" and arg:
            try:
                return self._session.reveal(arg)
            except Exception:
                return "not-found"
        if cmd == "CODE" and arg:
            r = self._session.current_code(arg)
            return r[0] if r else "no-totp"
        if cmd == "LOCK":
            self._locked = True
            return "locked"
        return "error unknown-command"

    def serve(self) -> None:
        if os.path.exists(self._path):
            os.unlink(self._path)
        srv = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        srv.bind(self._path)
        os.chmod(self._path, 0o600)
        srv.listen(1)
        srv.settimeout(self._timeout)
        print(f"ferrovault agent on {self._path} (idle lock {self._timeout}s)")
        try:
            while not self._locked:
                try:
                    conn, _ = srv.accept()
                except socket.timeout:
                    print("idle timeout - locking")
                    break
                with conn:
                    data = conn.recv(4096).decode("utf-8", "replace")
                    if data:
                        conn.sendall((self._handle(data) + "\n").encode())
        finally:
            self._session.lock()
            srv.close()
            if os.path.exists(self._path):
                os.unlink(self._path)
