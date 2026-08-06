import json
import subprocess
import uuid
from pathlib import Path

from app.config import (
    MAX_PDF_PAGES,
    OCR_DATA_DIR,
    TMP_DIR,
    WIN_PYTHON_EXE,
    WORKER_SCRIPT,
    WORKER_TIMEOUT_SEC,
)


class OcrWorkerError(RuntimeError):
    pass


def _to_wine_path(linux_path: Path) -> str:
    """Chuyển /home/... thành Z:\\home\\... (mapping ổ Z: mặc định của Wine)."""
    return "Z:" + str(linux_path).replace("/", "\\")


def run_ocr_on_image(image_path: Path) -> dict:
    """Gọi worker chạy dưới wine, trả về dict kết quả OCR cho 1 ảnh."""
    if not OCR_DATA_DIR.exists():
        raise OcrWorkerError(
            f"Thieu thu muc OCR_DATA_DIR ({OCR_DATA_DIR}). "
            "Hay copy oneocr.dll, oneocr.onemodel, onnxruntime.dll vao day."
        )

    cmd = [
        "wine",
        str(WIN_PYTHON_EXE),
        _to_wine_path(WORKER_SCRIPT),
        _to_wine_path(OCR_DATA_DIR),
        _to_wine_path(image_path),
    ]

    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=WORKER_TIMEOUT_SEC,
        )
    except subprocess.TimeoutExpired as exc:
        raise OcrWorkerError(f"Worker qua thoi gian cho phep ({WORKER_TIMEOUT_SEC}s)") from exc

    # stdout có thể lẫn log của wine ở stderr; chỉ parse dòng JSON cuối cùng của stdout
    stdout_lines = [line for line in proc.stdout.strip().splitlines() if line.strip()]
    if not stdout_lines:
        raise OcrWorkerError(
            f"Worker khong tra ve gi. exit_code={proc.returncode}\nstderr:\n{proc.stderr[-2000:]}"
        )

    try:
        payload = json.loads(stdout_lines[-1])
    except json.JSONDecodeError as exc:
        raise OcrWorkerError(
            f"Khong parse duoc JSON tu worker: {stdout_lines[-1][:500]}"
        ) from exc

    if not payload.get("ok"):
        raise OcrWorkerError(payload.get("error", "Loi khong xac dinh tu worker"))

    return payload["result"]


def new_job_dir() -> Path:
    job_dir = TMP_DIR / uuid.uuid4().hex
    job_dir.mkdir(parents=True, exist_ok=True)
    return job_dir


def run_ocr_dispatch(image_path: Path) -> dict:
    """Chọn backend theo OCR_BACKEND (native | wine | onnx).

    - native: chạy trên Windows native (không cần Wine) - gọi oneocr.dll
      thẳng trong process Python hiện tại bằng ctypes.WinDLL. Dùng khi bạn
      chạy uvicorn trực tiếp trên Windows (venv thường), không qua Docker.
    - wine:   dùng khi FastAPI chạy trong container Linux, gọi oneocr.dll
      qua subprocess Wine (xem run_ocr_on_image ở trên).
    - onnx:   pipeline ONNX thuần, không cần DLL/Wine.
    """
    from app.config import OCR_BACKEND

    if OCR_BACKEND == "onnx":
        from app.engine.onnx_pipeline.pipeline import get_pipeline
        return get_pipeline().run(image_path)

    if OCR_BACKEND == "native":
        return run_ocr_native(image_path)

    return run_ocr_on_image(image_path)


_native_engine = None


def run_ocr_native(image_path: Path) -> dict:
    """Chạy oneocr.dll trực tiếp trong process Python hiện tại (chỉ hoạt
    động khi Python đang chạy trên Windows thật, vì cần ctypes.WinDLL)."""
    global _native_engine

    import sys
    if sys.platform != "win32":
        raise OcrWorkerError(
            "OCR_BACKEND=native chi chay duoc tren Windows (can ctypes.WinDLL). "
            "Neu ban dang chay trong container Linux, doi sang OCR_BACKEND=wine."
        )

    if not OCR_DATA_DIR.exists():
        raise OcrWorkerError(
            f"Thieu thu muc OCR_DATA_DIR ({OCR_DATA_DIR}). "
            "Hay copy oneocr.dll, oneocr.onemodel, onnxruntime.dll vao day."
        )

    if _native_engine is None:
        # import cham (chi tren Windows) vi module dung ctypes.WinDLL,
        # se loi ngay khi import tren Linux
        sys.path.insert(0, str(WORKER_SCRIPT.parent))
        from ocr_worker import OneOcrEngine  # type: ignore

        try:
            _native_engine = OneOcrEngine(str(OCR_DATA_DIR))
        except Exception as exc:  # noqa: BLE001
            raise OcrWorkerError(f"Khoi tao OneOcrEngine that bai: {exc}") from exc

    try:
        return _native_engine.run(str(image_path))
    except Exception as exc:  # noqa: BLE001
        raise OcrWorkerError(f"OCR that bai: {exc}") from exc
