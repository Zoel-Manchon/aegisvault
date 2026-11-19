"""Design tokens: both modes complete, well formed and WCAG AA on every surface."""
import re

import pytest

from ferrovault.adapters.inbound.gui.design import tokens as t

HEX6 = re.compile(r"^#[0-9A-F]{6}$")
HEX8 = re.compile(r"^#[0-9A-F]{8}$")
SURFACES = ("BG_BASE", "SURFACE_1", "SURFACE_2", "SURFACE_3")


def _luminance(hex6: str) -> float:
    def channel(byte: str) -> float:
        c = int(byte, 16) / 255
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4

    h = hex6.lstrip("#")
    r, g, b = (channel(h[i:i + 2]) for i in (0, 2, 4))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(a: str, b: str) -> float:
    hi, lo = sorted((_luminance(a), _luminance(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


@pytest.mark.parametrize("pal", [t.DARK, t.LIGHT], ids=["dark", "light"])
def test_palette_values_are_well_formed(pal):
    for name, value in pal.colors().items():
        pattern = HEX8 if name == "SCRIM" else HEX6
        assert pattern.match(value), f"{pal.MODE}.{name} = {value!r}"


def test_palette_lookup():
    assert t.palette() is t.DARK
    assert t.palette("light") is t.LIGHT
    with pytest.raises(ValueError):
        t.palette("sepia")


@pytest.mark.parametrize("pal", [t.DARK, t.LIGHT], ids=["dark", "light"])
@pytest.mark.parametrize(
    "fg", ["TEXT_PRIMARY", "TEXT_SECONDARY", "TEXT_TERTIARY", "ACCENT", "SUCCESS", "WARNING", "DANGER", "INFO"]
)
def test_text_tokens_reach_aa_on_every_surface(pal, fg):
    for bg in SURFACES:
        ratio = contrast(getattr(pal, fg), getattr(pal, bg))
        assert ratio >= 4.5, f"{pal.MODE}: {fg} on {bg} is {ratio:.2f}:1"


@pytest.mark.parametrize("pal", [t.DARK, t.LIGHT], ids=["dark", "light"])
@pytest.mark.parametrize(
    "fg, bg",
    [
        ("ON_ACCENT", "ACCENT"),
        ("ON_ACCENT", "ACCENT_HOVER"),
        ("ON_ACCENT", "ACCENT_PRESSED"),
        ("ON_DANGER_SOLID", "DANGER_SOLID"),
        ("SUCCESS", "SUCCESS_BG"),
        ("WARNING", "WARNING_BG"),
        ("DANGER", "DANGER_BG"),
        ("INFO", "INFO_BG"),
        ("TEXT_PRIMARY", "SUCCESS_BG"),
        ("TEXT_PRIMARY", "WARNING_BG"),
        ("TEXT_PRIMARY", "DANGER_BG"),
        ("TEXT_PRIMARY", "INFO_BG"),
    ],
)
def test_text_on_filled_backgrounds_reaches_aa(pal, fg, bg):
    ratio = contrast(getattr(pal, fg), getattr(pal, bg))
    assert ratio >= 4.5, f"{pal.MODE}: {fg} on {bg} is {ratio:.2f}:1"


@pytest.mark.parametrize("pal", [t.DARK, t.LIGHT], ids=["dark", "light"])
@pytest.mark.parametrize("fg", ["BORDER_CONTROL", "SELECTION_BORDER", "FOCUS_RING"])
def test_control_boundaries_reach_3_to_1_on_every_surface(pal, fg):
    for bg in SURFACES:
        ratio = contrast(getattr(pal, fg), getattr(pal, bg))
        assert ratio >= 3.0, f"{pal.MODE}: {fg} on {bg} is {ratio:.2f}:1"


def test_alpha_helpers():
    assert t.qss_rgba("#0B0E14", 0.5) == "rgba(11, 14, 20, 128)"
    assert t.qcolor_hex("#05070B", 0.72) == "#B805070B"
    assert t.DARK.SCRIM == t.qcolor_hex("#05070B", 0.72)
    with pytest.raises(ValueError):
        t.qss_rgba("#FFF", 1)
    with pytest.raises(ValueError):
        t.qcolor_hex("#FFFFFF", 1.5)


def test_shadow_alpha_follows_mode():
    assert t.ELEVATION_3.color(t.DARK) == "#8C000000"
    assert t.ELEVATION_3.color(t.LIGHT) == "#2E000000"


def test_scales():
    assert [t.SPACE_1, t.SPACE_2, t.SPACE_4, t.SPACE_8, t.SPACE_16] == [4, 8, 16, 32, 64]
    assert t.RADIUS_XS < t.RADIUS_SM < t.RADIUS_MD < t.RADIUS_LG
    assert t.pill_radius(22) == 11
    assert min(t.CONTROL_H_SM, t.CONTROL_H_MD, t.CONTROL_H_LG) >= t.MIN_TARGET == 32
    assert "14px" in t.TYPE_BODY.qss() and "Inter" in t.TYPE_BODY.qss()
    assert "JetBrains Mono" in t.TYPE_MONO_CODE.qss()
