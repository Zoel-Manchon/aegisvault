#!/usr/bin/env bash
# Precompile bytecode so first launch skips .py -> .pyc compilation.
python -m compileall -q -j 0 src && python -m compileall -q "$(python -c 'import PySide6,os;print(os.path.dirname(PySide6.__file__))')" || true
echo "bytecode precompiled"
