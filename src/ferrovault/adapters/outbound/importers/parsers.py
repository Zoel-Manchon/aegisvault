"""Import parsers for other password managers.

Each parser turns an export file's text into a list of plain record dicts
({name, username, secret, url, notes, category}); the application layer adds
them to the vault. Pure parsing, no I/O beyond being handed the file text.
"""
from __future__ import annotations

import csv
import io
import json


def from_bitwarden_json(text: str) -> list:
    data = json.loads(text)
    folders = {f["id"]: f.get("name", "") for f in data.get("folders", [])}
    records = []
    for item in data.get("items", []):
        login = item.get("login") or {}
        uris = login.get("uris") or []
        records.append({
            "name": item.get("name", ""),
            "username": login.get("username", "") or "",
            "secret": login.get("password", "") or "",
            "url": (uris[0].get("uri", "") if uris else ""),
            "notes": item.get("notes", "") or "",
            "category": folders.get(item.get("folderId"), ""),
        })
    return records


_ALIASES = {
    "name": ("name", "title", "account"),
    "username": ("username", "user", "login_username", "login name", "email"),
    "secret": ("password", "secret", "login_password", "pass"),
    "url": ("url", "uri", "website", "login_uri"),
    "notes": ("notes", "note", "comments"),
    "category": ("category", "group", "folder", "type"),
}


def from_csv(text: str) -> list:
    reader = csv.DictReader(io.StringIO(text))
    headers = {h.lower().strip(): h for h in (reader.fieldnames or [])}

    def pick(row, field):
        for alias in _ALIASES[field]:
            if alias in headers:
                val = row.get(headers[alias])
                if val:
                    return val.strip()
        return ""

    records = []
    for row in reader:
        name = pick(row, "name")
        if name:
            records.append({f: pick(row, f) for f in _ALIASES})
    return records


_PARSERS = {"bitwarden": from_bitwarden_json, "csv": from_csv,
            "1password": from_csv, "keepass": from_csv}


def parse(fmt: str, text: str) -> list:
    try:
        return _PARSERS[fmt](text)
    except KeyError as exc:
        raise ValueError(f"unknown import format: {fmt}") from exc
