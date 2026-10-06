import shutil

from fastapi import APIRouter, File, HTTPException, Query, UploadFile

from app.engine.worker_bridge import OcrWorkerError, new_job_dir, run_ocr_dispatch_async
from app.models.schemas import Box, OcrImageResponse
from app.utils.bbox import VALID_FORMATS, convert_bbox

router = APIRouter(prefix="/ocr", tags=["OCR"])

ALLOWED_EXT = {".png", ".jpg", ".jpeg", ".bmp", ".tiff", ".webp"}


@router.post("/image", response_model=OcrImageResponse)
async def ocr_image(
    file: UploadFile = File(...),
    bbox_format: str = Query("xyxy"),
    getContent: bool = Query(False),
):
    if bbox_format not in VALID_FORMATS:
        raise HTTPException(400, f"bbox_format khong hop le: {bbox_format}. Cho phep: {sorted(VALID_FORMATS)}")

    ext = "." + file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
    if ext not in ALLOWED_EXT:
        raise HTTPException(400, f"Dinh dang khong ho tro: {ext}. Ho tro: {sorted(ALLOWED_EXT)}")

    job_dir = new_job_dir()
    image_path = job_dir / f"input{ext}"
    try:
        with image_path.open("wb") as f:
            shutil.copyfileobj(file.file, f)

        raw_result = await run_ocr_dispatch_async(image_path)

        boxes = [
            Box(
                text=line["text"],
                score=line.get("confidence", 0.0),
                bbox=convert_bbox(line.get("bbox"), bbox_format),
            )
            for line in raw_result.get("lines", [])
        ]

        return OcrImageResponse(
            image_name=file.filename,
            bbox_format=bbox_format,
            boxes=boxes,
            content=raw_result.get("text", "") if getContent else None,
        )
    except (OcrWorkerError, FileNotFoundError, RuntimeError) as exc:
        raise HTTPException(500, str(exc)) from exc
    finally:
        shutil.rmtree(job_dir, ignore_errors=True)