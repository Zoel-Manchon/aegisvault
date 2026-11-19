"""Write the Windows .ico for the build from the same drawing as the window icon.

    python packaging/windows/make_icon.py build/windows/aegisvault.ico
"""
import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from PySide6.QtGui import QGuiApplication  # noqa: E402

from ferrovault.adapters.inbound.gui.app_icon import ico_bytes  # noqa: E402


def main(target: str) -> int:
    _app = QGuiApplication([])
    path = Path(target)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(ico_bytes())
    print(f"icon: {path} ({path.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: make_icon.py OUTPUT.ico")
    raise SystemExit(main(sys.argv[1]))
