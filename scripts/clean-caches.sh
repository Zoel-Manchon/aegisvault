#!/usr/bin/env bash
set -euo pipefail

ROOT="${1:-.}"
cd "$ROOT"

find . -type d \( \
  -name '__pycache__' -o \
  -name '.pytest_cache' -o \
  -name '.mypy_cache' -o \
  -name '.ruff_cache' -o \
  -name '.tox' -o \
  -name '.nox' -o \
  -name '.venv' -o \
  -name 'target' -o \
  -name 'build' -o \
  -name 'dist' -o \
  -name '*.egg-info' \
\) -prune -exec rm -rf {} +

find . -type f \( \
  -name '*.pyc' -o \
  -name '*.pyo' -o \
  -name '.coverage' -o \
  -name 'coverage.xml' \
\) -delete

echo "AegisVault caches removed."
