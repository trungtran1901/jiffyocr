import asyncio
import shutil

import fitz
from fastapi import APIRouter, File, HTTPException, Query, UploadFile

from app.config import MAX_PDF_PAGES, PDF_RENDER_DPI
from app.engine.worker_bridge import OcrWorkerError, new_job_dir, run_ocr_dispatch_async
from app.models.schemas import Box, ImagePageResult, OcrPdfResponse
from app.utils.bbox import VALID_FORMATS, convert_bbox

router = APIRouter(prefix="/ocr", tags=["OCR"])

PAGE_CONCURRENCY = 4


async def _ocr_one_page(job_dir, page, i, bbox_format, getContent, matrix, semaphore):
    async with semaphore:
        try:
            pix = await asyncio.to_thread(page.get_pixmap, matrix=matrix, colorspace=fitz.csRGB)
            img_path = job_dir / f"page_{i}.png"
            await asyncio.to_thread(pix.save, img_path)

            raw_result = await run_ocr_dispatch_async(img_path)
            img_path.unlink(missing_ok=True)

            boxes = [
                Box(
                    text=line["text"],
                    score=line.get("confidence", 0.0),
                    bbox=convert_bbox(line.get("bbox"), bbox_format),
                )
                for line in raw_result.get("lines", [])
            ]

            return ImagePageResult(
                page_index=i,
                source="ocr",
                boxes=boxes,
                content=raw_result.get("text", "") if getContent else None,
            )
        except (OcrWorkerError, RuntimeError) as exc:
            return ImagePageResult(
                page_index=i,
                source="ocr_error",
                boxes=[],
                content=f"[loi trang {i}]: {exc}" if getContent else None,
            )


@router.post("/pdf", response_model=OcrPdfResponse)
async def ocr_pdf(
    file: UploadFile = File(...),
    bbox_format: str = Query("xyxy"),
    getContent: bool = Query(False),
):
    if bbox_format not in VALID_FORMATS:
        raise HTTPException(400, f"bbox_format khong hop le: {bbox_format}. Cho phep: {sorted(VALID_FORMATS)}")

    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(400, "Chi ho tro file .pdf")

    job_dir = new_job_dir()
    pdf_path = job_dir / "input.pdf"
    try:
        with pdf_path.open("wb") as f:
            shutil.copyfileobj(file.file, f)

        doc = fitz.open(pdf_path)
        if doc.page_count > MAX_PDF_PAGES:
            raise HTTPException(400, f"PDF co {doc.page_count} trang, vuot gioi han {MAX_PDF_PAGES} trang/lan.")

        zoom = PDF_RENDER_DPI / 72
        matrix = fitz.Matrix(zoom, zoom)
        semaphore = asyncio.Semaphore(PAGE_CONCURRENCY)

        tasks = [
            _ocr_one_page(job_dir, page, i, bbox_format, getContent, matrix, semaphore)
            for i, page in enumerate(doc)
        ]
        result_pages = await asyncio.gather(*tasks)

        return OcrPdfResponse(
            filename=file.filename,
            bbox_format=bbox_format,
            page_count=doc.page_count,
            pages=list(result_pages),
        )
    except (OcrWorkerError, FileNotFoundError, RuntimeError) as exc:
        raise HTTPException(500, str(exc)) from exc
    finally:
        shutil.rmtree(job_dir, ignore_errors=True)