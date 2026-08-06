#!/bin/bash
set -euo pipefail

WIN_PYTHON_VERSION="3.11.9"
WIN_PYTHON_DIR="/opt/win-python"
WIN_PYTHON_ZIP="python-${WIN_PYTHON_VERSION}-embed-amd64.zip"
WIN_PYTHON_URL="https://www.python.org/ftp/python/${WIN_PYTHON_VERSION}/${WIN_PYTHON_ZIP}"

mkdir -p "$WIN_PYTHON_DIR"
cd "$WIN_PYTHON_DIR"

echo "[1/3] Tai Windows Python embeddable ${WIN_PYTHON_VERSION}..."
curl -fsSL -o "$WIN_PYTHON_ZIP" "$WIN_PYTHON_URL"
unzip -q "$WIN_PYTHON_ZIP"
rm "$WIN_PYTHON_ZIP"

echo "[2/3] Tai Pillow (wheel Windows/CPython) bang pip Linux, khong qua Wine..."
WHEEL_DIR=$(mktemp -d)
python3 -m pip download --no-deps --only-binary=:all: \
    --python-version 311 --implementation cp --abi cp311 --platform win_amd64 \
    -d "$WHEEL_DIR" Pillow==10.4.0

echo "[3/3] Giai nen Pillow thang vao thu muc Windows Python..."
python3 -m zipfile -e "$WHEEL_DIR"/pillow-*.whl "$WIN_PYTHON_DIR/"
rm -rf "$WHEEL_DIR"

echo "Xong. Windows Python o: $WIN_PYTHON_DIR"