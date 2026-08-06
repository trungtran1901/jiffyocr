import shutil

import fitz
import pdf_inspector
from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile

from app.config import MAX_PDF_PAGES, PDF_RENDER_DPI
from app.engine.worker_bridge import OcrWorkerError, new_job_dir, run_ocr_dispatch
from app.models.schemas import Box, ImagePageResult, PdfFastResponse
from app.utils.bbox import VALID_FORMATS, convert_bbox
# from app.utils.pdf_pages import parse_pages_param

router = APIRouter(prefix="/ocr", tags=["OCR"])

TRUE_VALUES = {"1", "true", "yes", "on"}


def _resolve_bool(query_val, form_val, default=False):
    for val in (query_val, form_val):
        if val is None:
            continue
        if isinstance(val, bool):
            return val
        return str(val).strip().lower() in TRUE_VALUES
    return default


def _resolve_str(query_val, form_val, default):
    for val in (query_val, form_val):
        if val:
            return val
    return default


def _group_text_items_by_page(items, page_count):
    grouped = {i: [] for i in range(page_count)}
    if not items:
        return grouped

    pages_seen = [item.page for item in items]
    offset = 1 if min(pages_seen) == 1 else 0

    for item in items:
        idx = item.page - offset
        if 0 <= idx < page_count:
            grouped[idx].append(item)
    return grouped


def _text_items_to_boxes(items, bbox_format):
    boxes = []
    for item in items:
        quad = {
            "x1": item.x, "y1": item.y,
            "x2": item.x + item.width, "y2": item.y,
            "x3": item.x + item.width, "y3": item.y + item.height,
            "x4": item.x, "y4": item.y + item.height,
        }
        boxes.append(Box(text=item.text, score=1.0, bbox=convert_bbox(quad, bbox_format)))
    return boxes


@router.post("/pdf-fast", response_model=PdfFastResponse)
async def ocr_pdf_fast(
    file: UploadFile = File(...),
    bbox_format_q: str = Query(None, alias="bbox_format"),
    bbox_format_f: str = Form(None, alias="bbox_format"),
    getContent_q: str = Query(None, alias="getContent"),
    getContent_f: str = Form(None, alias="getContent"),
    pages_q: str = Query(None, alias="pages"),
    pages_f: str = Form(None, alias="pages"),
):
    bbox_format = _resolve_str(bbox_format_q, bbox_format_f, "xyxy")
    getContent = _resolve_bool(getContent_q, getContent_f, False)
    pages = _resolve_str(pages_q, pages_f, None)

    if bbox_format not in VALID_FORMATS:
        raise HTTPException(400, f"bbox_format khong hop le: {bbox_format}. Cho phep: {sorted(VALID_FORMATS)}")

    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(400, "Chi ho tro file .pdf")

    job_dir = new_job_dir()
    pdf_path = job_dir / "input.pdf"
    try:
        with pdf_path.open("wb") as f:
            shutil.copyfileobj(file.file, f)

        inspect_result = pdf_inspector.process_pdf(str(pdf_path))
        pages_needing_ocr_1idx = set(getattr(inspect_result, "pages_needing_ocr", []) or [])

        doc = fitz.open(pdf_path)
        if doc.page_count > MAX_PDF_PAGES:
            raise HTTPException(400, f"PDF co {doc.page_count} trang, vuot gioi han {MAX_PDF_PAGES} trang/lan.")

        # selected_pages = parse_pages_param(pages, doc.page_count)

        text_items_by_page = {}
        if hasattr(pdf_inspector, "extract_text_with_positions"):
            all_items = pdf_inspector.extract_text_with_positions(str(pdf_path))
            text_items_by_page = _group_text_items_by_page(all_items, doc.page_count)

        zoom = PDF_RENDER_DPI / 72
        matrix = fitz.Matrix(zoom, zoom)

        result_pages = []
        for i, page in enumerate(doc):
            # if i not in selected_pages:
            #     continue

            page_number_1indexed = i + 1
            needs_ocr = page_number_1indexed in pages_needing_ocr_1idx

            if not needs_ocr:
                items = text_items_by_page.get(i, [])
                native_text = page.get_text()

                if items:
                    boxes = _text_items_to_boxes(items, bbox_format)
                else:
                    boxes = []

                content = native_text if getContent else None

                result_pages.append(
                    ImagePageResult(
                        page_index=i,
                        source="text",
                        boxes=boxes,
                        content=content,
                    )
                )
                continue

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

        return PdfFastResponse(
            filename=file.filename,
            bbox_format=bbox_format,
            pdf_type=str(getattr(inspect_result, "pdf_type", "unknown")),
            page_count=doc.page_count,
            pages=result_pages,
        )
    except (OcrWorkerError, FileNotFoundError, RuntimeError) as exc:
        raise HTTPException(500, str(exc)) from exc
    finally:
        shutil.rmtree(job_dir, ignore_errors=True)