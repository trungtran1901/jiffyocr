import shutil

import fitz
from fastapi import APIRouter, File, HTTPException, Query, UploadFile

from app.config import MAX_PDF_PAGES, PDF_RENDER_DPI
from app.engine.worker_bridge import OcrWorkerError, new_job_dir, run_ocr_dispatch
from app.models.schemas import Box, ImagePageResult, OcrPdfResponse
from app.utils.bbox import VALID_FORMATS, convert_bbox
# from app.utils.pdf_pages import parse_pages_param

router = APIRouter(prefix="/ocr", tags=["OCR"])


@router.post("/pdf", response_model=OcrPdfResponse)
async def ocr_pdf(
    file: UploadFile = File(...),
    bbox_format: str = Query("xyxy"),
    getContent: bool = Query(False),
    pages: str = Query(None),
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

        # selected_pages = parse_pages_param(pages, doc.page_count)

        zoom = PDF_RENDER_DPI / 72
        matrix = fitz.Matrix(zoom, zoom)

        result_pages = []
        for i, page in enumerate(doc):
            # if i not in selected_pages:
            #     continue

            try:
                pix = page.get_pixmap(matrix=matrix, colorspace=fitz.csRGB)
                img_path = job_dir / f"page_{i}.png"
                pix.save(img_path)
                pix = None

                raw_result = run_ocr_dispatch(img_path)
                img_path.unlink(missing_ok=True)

                boxes = [
                    Box(
                        text=line["text"],
                        score=line.get("confidence", 0.0),
                        bbox=convert_bbox(line.get("bbox"), bbox_format),
                    )
                    for line in raw_result.get("lines", [])
                ]

                result_pages.append(
                    ImagePageResult(
                        page_index=i,
                        source="ocr",
                        boxes=boxes,
                        content=raw_result.get("text", "") if getContent else None,
                    )
                )
            except (OcrWorkerError, RuntimeError) as exc:
                result_pages.append(
                    ImagePageResult(
                        page_index=i,
                        source="ocr_error",
                        boxes=[],
                        content=f"[loi trang {i}]: {exc}" if getContent else None,
                    )
                )

        return OcrPdfResponse(
            filename=file.filename,
            bbox_format=bbox_format,
            page_count=doc.page_count,
            pages=result_pages,
        )
    except (OcrWorkerError, FileNotFoundError, RuntimeError) as exc:
        raise HTTPException(500, str(exc)) from exc
    finally:
        shutil.rmtree(job_dir, ignore_errors=True)