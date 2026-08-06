import os
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

_DEFAULT_BACKEND = "native" if sys.platform == "win32" else "wine"
OCR_BACKEND = os.environ.get("OCR_BACKEND", _DEFAULT_BACKEND)

OCR_DATA_DIR = Path(os.environ.get("OCR_DATA_DIR", BASE_DIR / "ocr_data"))

WINE_PREFIX = os.environ.get("WINEPREFIX", "/root/.wine")
WIN_PYTHON_DIR = Path(os.environ.get("WIN_PYTHON_DIR", "/opt/win-python"))
WIN_PYTHON_EXE = WIN_PYTHON_DIR / "python.exe"

WORKER_SCRIPT = BASE_DIR / "app" / "engine" / "win" / "ocr_worker.py"

_default_tmp = str(BASE_DIR / "tmp_jobs") if sys.platform == "win32" else "/tmp/oneocr_jobs"
TMP_DIR = Path(os.environ.get("OCR_TMP_DIR", _default_tmp))
TMP_DIR.mkdir(parents=True, exist_ok=True)

WORKER_TIMEOUT_SEC = int(os.environ.get("OCR_WORKER_TIMEOUT", "60"))

MAX_PDF_PAGES = int(os.environ.get("OCR_MAX_PDF_PAGES", "500"))

PDF_RENDER_DPI = int(os.environ.get("OCR_PDF_DPI", "220"))