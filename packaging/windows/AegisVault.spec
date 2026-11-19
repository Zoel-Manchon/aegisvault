# PyInstaller spec for the AegisVault desktop app on Windows: one windowed AegisVault.exe.
#
#     .venv\Scripts\python -m PyInstaller --noconfirm --clean packaging\windows\AegisVault.spec
#
# scripts\build-exe.ps1 runs exactly this and prints the SHA-256 of the result.
# What goes in is the Qt Widgets app and the Python crypto adapters (Argon2id and
# AES-256-GCM from `cryptography`). The Rust core is picked up when `ferrocrypto`
# is installed in the build environment, and left out otherwise. Qt Quick, the
# network module, software OpenGL and Qt's translations stay out: the window
# does not use them, and every DLL that is not shipped is one less to load.
import subprocess
import sys
from pathlib import Path

from PyInstaller.utils.win32.versioninfo import (
    FixedFileInfo, StringFileInfo, StringStruct, StringTable, VarFileInfo, VarStruct, VSVersionInfo,
)

HERE = Path(SPECPATH)
ROOT = HERE.parents[1]
SRC = ROOT / "src"
GUI = SRC / "ferrovault" / "adapters" / "inbound" / "gui"
sys.path.insert(0, str(SRC))
from ferrovault import __version__  # noqa: E402

# ---- icon: drawn by the app's own code, so the .exe and the window always match -------------
ICON = Path(workpath) / "aegisvault.ico"
subprocess.run([sys.executable, str(HERE / "make_icon.py"), str(ICON)], check=True)

# ---- what Windows shows under Properties > Details -------------------------------------------
numbers = tuple(int(part) for part in __version__.split(".")[:3])
numbers = numbers + (0,) * (4 - len(numbers))
VERSION = VSVersionInfo(
    ffi=FixedFileInfo(filevers=numbers, prodvers=numbers, mask=0x3F, flags=0x0, OS=0x40004,
                      fileType=0x1, subtype=0x0, date=(0, 0)),
    kids=[
        StringFileInfo([StringTable("0C0A04B0", [
            StringStruct("CompanyName", "AegisVault"),
            StringStruct("FileDescription", "AegisVault: bóveda cifrada de contraseñas y claves"),
            StringStruct("FileVersion", __version__),
            StringStruct("InternalName", "AegisVault"),
            StringStruct("LegalCopyright", "MIT License"),
            StringStruct("OriginalFilename", "AegisVault.exe"),
            StringStruct("ProductName", "AegisVault"),
            StringStruct("ProductVersion", __version__),
        ])]),
        VarFileInfo([VarStruct("Translation", [0x0C0A, 1200])]),
    ],
)

a = Analysis(
    [str(HERE / "launcher.py")],
    pathex=[str(SRC)],
    binaries=[],
    datas=[(str(GUI / "fonts" / "Inter.ttf"), "ferrovault/adapters/inbound/gui/fonts")],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "tkinter", "_tkinter",
        # the experimental QML shell and everything it alone needs
        "ferrovault.adapters.inbound.gui.qml_app", "ferrovault.adapters.inbound.gui.qml_bridge",
        "PySide6.QtQml", "PySide6.QtQuick", "PySide6.QtQuickWidgets", "PySide6.QtQuickControls2",
        "PySide6.QtNetwork", "PySide6.QtOpenGL", "PySide6.QtOpenGLWidgets", "PySide6.QtDBus",
    ],
    noarchive=False,
    optimize=0,
)

# Files the Qt hooks collect that this window never loads.
DROP = (
    "opengl32sw.dll",                     # software OpenGL; the widgets paint without OpenGL
    "qt6pdf.dll",                         # only the PDF image plug-in below needs it
    "plugins/generic/qtuiotouchplugin",   # touch input over UDP: a network listener nobody needs
    "qt6network.dll",                     # only that touch plug-in needs it
    "plugins/imageformats/qpdf", "plugins/imageformats/qicns", "plugins/imageformats/qtga",
    "plugins/imageformats/qtiff", "plugins/imageformats/qwbmp",
    "plugins/platforms/qdirect2d", "plugins/platforms/qminimal", "plugins/platforms/qoffscreen",
    "/translations/",                     # Qt's own strings; the app carries its Spanish text
)


def _keep(entry) -> bool:
    name = "/" + entry[0].replace("\\", "/").lower()
    return not any(part in name for part in DROP)


a.binaries = [entry for entry in a.binaries if _keep(entry)]
a.datas = [entry for entry in a.datas if _keep(entry)]

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="AegisVault",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,              # packed executables trip antivirus heuristics and gain nothing here
    runtime_tmpdir=None,    # PyInstaller's per-user, access-restricted temporary folder
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(ICON),
    version=VERSION,
    uac_admin=False,        # a password manager never needs administrator rights
)
