"""Entry point that PyInstaller freezes into AegisVault.exe: the desktop window."""
import sys

from ferrovault.adapters.inbound.gui.app import main

if __name__ == "__main__":
    sys.exit(main())
