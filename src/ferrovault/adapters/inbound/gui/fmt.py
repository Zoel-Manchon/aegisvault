"""Spanish display formatting for the GUI: dates, relative ages, plurals, hosts.

Qt-free so it can be unit-tested. Timestamps in the vault are ISO-8601 (UTC);
everything shown to the user is converted to local time.
"""
from __future__ import annotations

from datetime import datetime, timezone
from urllib.parse import urlparse

MONTHS = ("ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic")

KIND_LABELS = {"login": "Login", "api_key": "API key", "note": "Nota segura", "card": "Tarjeta"}
SECRET_LABELS = {"login": "Contraseña", "api_key": "Clave", "note": "Contenido", "card": "Número"}
USER_LABELS = {"login": "Usuario", "api_key": "Cuenta", "note": "Título", "card": "Titular"}


def parse_iso(value: str) -> datetime | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _local(dt: datetime) -> datetime:
    try:
        return dt.astimezone()
    except (OverflowError, OSError, ValueError):
        return dt


def fmt_date(value: str) -> str:
    """'2025-09-12T…' -> '12 sep 2025'."""
    dt = parse_iso(value)
    if dt is None:
        return ""
    dt = _local(dt)
    return f"{dt.day} {MONTHS[dt.month - 1]} {dt.year}"


def fmt_datetime(value: str, seconds: bool = True) -> str:
    """'…' -> '18 nov 2026 · 10:42:07'."""
    dt = parse_iso(value)
    if dt is None:
        return ""
    dt = _local(dt)
    clock = dt.strftime("%H:%M:%S" if seconds else "%H:%M")
    return f"{fmt_date(value)} · {clock}"


def fmt_short_date(value: str) -> str:
    """'…' -> '12 nov' (same year) or '12 nov 2024'."""
    dt = parse_iso(value)
    if dt is None:
        return ""
    dt = _local(dt)
    if dt.year == datetime.now().year:
        return f"{dt.day} {MONTHS[dt.month - 1]}"
    return f"{dt.day} {MONTHS[dt.month - 1]} {dt.year}"


def days_since(value: str, now: datetime | None = None) -> int | None:
    dt = parse_iso(value)
    if dt is None:
        return None
    now = now or datetime.now(timezone.utc)
    return max(0, (now - dt).days)


def ago(value: str, now: datetime | None = None) -> str:
    """Relative age in Spanish: 'hace 3 min', 'hace 14 meses', 'hoy'."""
    dt = parse_iso(value)
    if dt is None:
        return ""
    now = now or datetime.now(timezone.utc)
    seconds = max(0, int((now - dt).total_seconds()))
    if seconds < 60:
        return "hace un momento"
    minutes = seconds // 60
    if minutes < 60:
        return f"hace {minutes} min"
    hours = minutes // 60
    if hours < 24:
        return f"hace {hours} h"
    days = hours // 24
    if days == 1:
        return "ayer"
    if days < 31:
        return f"hace {days} días"
    months = days // 30
    if months < 12:
        return "hace 1 mes" if months == 1 else f"hace {months} meses"
    years = days // 365
    if months < 24:
        return f"hace {months} meses"
    return f"hace {years} años"


def plural(n: int, one: str, many: str) -> str:
    return f"{n} {one if n == 1 else many}"


def thousands(n: int) -> str:
    """Spanish digit grouping with a thin space: 1287 -> '1 287'."""
    return f"{n:,}".replace(",", " ")


def host_of(url: str) -> str:
    if not url:
        return ""
    parsed = urlparse(url if "://" in url else f"https://{url}")
    host = parsed.hostname or url
    return host[4:] if host.startswith("www.") else host


def safe_web_url(url: str) -> str | None:
    """Only http(s) URLs may be opened from the vault (no file:, javascript:, …)."""
    if not url:
        return None
    candidate = url if "://" in url else f"https://{url}"
    parsed = urlparse(candidate)
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        return None
    return candidate


def join_names(names, limit: int = 3) -> str:
    """['A', 'B', 'C'] -> '«A», «B» y «C»'."""
    names = [f"«{n}»" for n in names]
    if len(names) > limit:
        rest = len(names) - limit + 1
        names = names[: limit - 1] + [f"{rest} más"]
    if len(names) <= 1:
        return "".join(names)
    return ", ".join(names[:-1]) + " y " + names[-1]


NUMBER_WORDS = {2: "dos", 3: "tres", 4: "cuatro", 5: "cinco", 6: "seis"}


def count_word(n: int) -> str:
    return NUMBER_WORDS.get(n, str(n))


# The starter Zero Trust rules ship with English names and reasons (the CLI and
# saved settings use them). The GUI shows them in Spanish unless they were edited.
_STARTER_RULE_TEXT = {
    "Critical secrets need MFA + trusted device": "Secretos críticos: MFA y dispositivo de confianza",
    "Production sharing requires approval context": "Compartir en Producción, bloqueado",
    "Critical audit export guard": "Sin exportar auditoría de lo crítico",
    "Critical secrets require verified MFA and a trusted device.":
        "Los secretos críticos piden MFA verificado y un dispositivo de confianza.",
    "Production vault sharing is blocked by the local Zero Trust policy pack.":
        "Compartir desde la bóveda de Producción está bloqueado por la política local.",
    "Critical policy blocks this export path.": "La política de secretos críticos bloquea esta exportación.",
}


def starter_rule_text(text: str) -> str:
    return _STARTER_RULE_TEXT.get(text or "", text or "")
