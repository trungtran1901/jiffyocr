import asyncio
import shutil

import fitz
import pdf_inspector
from fastapi import APIRouter, File, HTTPException, Query, UploadFile

from app.config import MAX_PDF_PAGES, PDF_RENDER_DPI
from app.engine.worker_bridge import OcrWorkerError, new_job_dir, run_ocr_dispatch_async
from app.models.schemas import Box, ImagePageResult, PdfFastResponse
from app.utils.bbox import VALID_FORMATS, convert_bbox

router = APIRouter(prefix="/ocr", tags=["OCR"])

PAGE_CONCURRENCY = 4


def _is_noise(text):
    t = (text or "").strip()
    return not t or t.startswith("[Image:")


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
        if _is_noise(item.text):
            continue
        quad = {
            "x1": item.x, "y1": item.y,
            "x2": item.x + item.width, "y2": item.y,
            "x3": item.x + item.width, "y3": item.y + item.height,
            "x4": item.x, "y4": item.y + item.height,
        }
        boxes.append(Box(text=item.text, score=1.0, bbox=convert_bbox(quad, bbox_format)))
    return boxes


def _detect_column_splits(items, min_gap=12.0):
    spans = sorted((it.x, it.x + it.width) for it in items)
    merged = []
    for x0, x1 in spans:
        if merged and x0 <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], x1)
        else:
            merged.append([x0, x1])
    return [(a[1] + b[0]) / 2 for a, b in zip(merged, merged[1:]) if b[0] - a[1] >= min_gap]


def _lines_from_items(items):
    items = sorted(items, key=lambda it: -(it.y + it.height / 2))
    lines, cur, cur_y, cur_h = [], [], None, None
    for it in items:
        cy = it.y + it.height / 2
        if cur and abs(cy - cur_y) <= max(cur_h, it.height) * 0.5:
            cur.append(it)
        else:
            if cur:
                lines.append(cur)
            cur, cur_y, cur_h = [it], cy, it.height
    if cur:
        lines.append(cur)

    out = []
    for line in lines:
        line.sort(key=lambda it: it.x)
        parts = []
        for it in line:
            txt = it.text.strip()
            if not txt:
                continue
            if parts and parts[-1] in ("•", "-", "–"):
                parts[-1] = parts[-1] + " " + txt
            else:
                parts.append(txt)
        if parts:
            out.append(" ".join(parts))
    return out


def _items_to_content(items, split_columns=True):
    items = [it for it in items if not _is_noise(it.text)]
    if not items:
        return ""

    splits = _detect_column_splits(items) if split_columns else []
    if not splits:
        return "\n".join(_lines_from_items(items))

    cols = [[] for _ in range(len(splits) + 1)]
    for it in items:
        cols[sum(it.x >= s for s in splits)].append(it)
    return "\n\n".join("\n".join(_lines_from_items(c)) for c in cols if c)


async def _process_page(job_dir, page, i, needs_ocr, has_table, text_items_by_page, bbox_format, getContent, matrix, semaphore):
    if not needs_ocr:
        items = text_items_by_page.get(i, [])
        boxes = _text_items_to_boxes(items, bbox_format) if items else []

        content = None
        if getContent:
            if items:
                content = _items_to_content(items, split_columns=not has_table)
            else:
                content = await asyncio.to_thread(page.get_text, "text", sort=True)

        return ImagePageResult(page_index=i, source="text", boxes=boxes, content=content)

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


@router.post("/pdf-fast", response_model=PdfFastResponse)
async def ocr_pdf_fast(
    file: UploadFile = File(...),
    bbox_format: str = Query("xyxy"),
    getContent: bool = Query(False),
    getContentFullDoc: bool = Query(False),
):
    if bbox_format not in VALID_FORMATS:
        raise HTTPException(400, f"bbox_format khong hop le: {bbox_format}. Cho phep: {sorted(VALID_FORMATS)}")

    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(400, "Chi ho tro file .pdf")

    need_content = getContent or getContentFullDoc

    job_dir = new_job_dir()
    pdf_path = job_dir / "input.pdf"
    doc = None
    try:
        with pdf_path.open("wb") as f:
            shutil.copyfileobj(file.file, f)

        doc = fitz.open(pdf_path)
        page_count = doc.page_count
        if page_count > MAX_PDF_PAGES:
            raise HTTPException(400, f"PDF co {page_count} trang, vuot gioi han {MAX_PDF_PAGES} trang/lan.")

        inspect_result = await asyncio.to_thread(pdf_inspector.process_pdf, str(pdf_path))
        pages_needing_ocr_1idx = set(getattr(inspect_result, "pages_needing_ocr", []) or [])
        pages_with_tables_1idx = set(getattr(inspect_result, "pages_with_tables", []) or [])

        text_items_by_page = {}
        if hasattr(pdf_inspector, "extract_text_with_positions"):
            all_items = await asyncio.to_thread(pdf_inspector.extract_text_with_positions, str(pdf_path))
            text_items_by_page = _group_text_items_by_page(all_items, page_count)

        zoom = PDF_RENDER_DPI / 72
        matrix = fitz.Matrix(zoom, zoom)
        semaphore = asyncio.Semaphore(PAGE_CONCURRENCY)

        tasks = [
            _process_page(
                job_dir, page, i,
                (i + 1) in pages_needing_ocr_1idx,
                (i + 1) in pages_with_tables_1idx,
                text_items_by_page, bbox_format, need_content, matrix, semaphore,
            )
            for i, page in enumerate(doc)
        ]
        result_pages = list(await asyncio.gather(*tasks))

        full_content = None
        if getContentFullDoc:
            full_content = "\n\n".join(p.content for p in result_pages if p.content)

        if not getContent:
            for p in result_pages:
                p.content = None

        return PdfFastResponse(
            filename=file.filename,
            bbox_format=bbox_format,
            pdf_type=str(getattr(inspect_result, "pdf_type", "unknown")),
            page_count=page_count,
            pages=result_pages,
            content=full_content,
        )
    except (OcrWorkerError, FileNotFoundError, RuntimeError) as exc:
        raise HTTPException(500, str(exc)) from exc
    finally:
        if doc is not None:
            doc.close()
        shutil.rmtree(job_dir, ignore_errors=True)