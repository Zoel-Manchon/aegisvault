"""The desktop entry point: the icon the Windows build embeds, and a clean exit.

The exit test runs ``app.main()`` in a child process (it creates its own
QApplication) with the settings folder sandboxed, closes the window once it is
up and checks that no window outlives ``main()``. Windows left to interpreter
shutdown were destroyed after the QApplication and crashed the process on
exit about half the time on Windows.
"""
import os
import struct
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")
pytest.importorskip("cryptography")

from PySide6.QtWidgets import QApplication  # noqa: E402

_app = QApplication.instance() or QApplication([])

from ferrovault.adapters.inbound.gui.app_icon import SIZES, app_icon, ico_bytes, render  # noqa: E402

SRC = Path(__file__).resolve().parents[2] / "src"
PNG = b"\x89PNG\r\n\x1a\n"


def test_the_icon_file_holds_every_size_as_png():
    data = ico_bytes()
    reserved, kind, count = struct.unpack_from("<HHH", data, 0)
    assert (reserved, kind, count) == (0, 1, len(SIZES))
    end = 6 + 16 * count
    for index, size in enumerate(SIZES):
        width, height, _colours, _zero, planes, bits, length, offset = struct.unpack_from(
            "<BBBBHHII", data, 6 + 16 * index)
        assert width == height == (0 if size == 256 else size)
        assert (planes, bits) == (1, 32)
        assert offset == end and data[offset:offset + 8] == PNG
        end = offset + length
    assert end == len(data)


def test_the_icon_is_drawn_at_every_size():
    for size in (16, 32, 256):
        image = render(size)
        assert image.width() == image.height() == size
        assert image.pixelColor(size // 2, size // 2).alpha() == 255, "the tile fills the middle"
        assert image.pixelColor(0, 0).alpha() < 255, "the corners are rounded"
    assert {s.width() for s in app_icon().availableSizes()} >= {16, 32, 256}


_EXIT_SCRIPT = textwrap.dedent("""
    import sys
    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QApplication
    import ferrovault.adapters.inbound.gui.app as A

    class AutoClose(QApplication):
        def exec(self):
            def close_when_ready():
                windows = [w for w in QApplication.topLevelWidgets() if w.isVisible()]
                if any(type(w).__name__ == "UnlockWindow" for w in windows):
                    for window in windows:
                        window.close()
                else:
                    QTimer.singleShot(50, close_when_ready)
            QTimer.singleShot(50, close_when_ready)
            return super().exec()

    A.QApplication = AutoClose
    code = A.main(["aegisvault-gui"])
    print("windows left:", len(QApplication.topLevelWidgets()))
    sys.exit(code)
""")


def test_main_destroys_its_windows_before_returning(tmp_path):
    env = dict(os.environ, QT_QPA_PLATFORM="offscreen", PYTHONPATH=str(SRC),
               APPDATA=str(tmp_path / "appdata"), LOCALAPPDATA=str(tmp_path / "localappdata"),
               HOME=str(tmp_path), USERPROFILE=str(tmp_path))
    result = subprocess.run([sys.executable, "-c", _EXIT_SCRIPT], env=env, capture_output=True, text=True,
                            timeout=120)
    assert result.returncode == 0, result.stderr[-2000:]
    assert "windows left: 0" in result.stdout, result.stdout + result.stderr[-2000:]
