import shutil

import pdf_inspector
from fastapi import APIRouter, File, HTTPException, UploadFile

from app.engine.worker_bridge import new_job_dir
from app.models.schemas import LayoutDetectResponse, PageLayoutInfo, TableBox, TableDetectResponse

router = APIRouter(prefix="/layout", tags=["Layout"])
table_router = APIRouter(prefix="/table", tags=["Table"])


def _inspect(pdf_path):
    if hasattr(pdf_inspector, "detect_pdf"):
        try:
            return pdf_inspector.detect_pdf(str(pdf_path), analyze=True)
        except TypeError:
            return pdf_inspector.detect_pdf(str(pdf_path))
    return pdf_inspector.process_pdf(str(pdf_path))


@router.post("/detect", response_model=LayoutDetectResponse)
async def detect_layout(file: UploadFile = File(...)):
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(400, "Chi ho tro file .pdf")

    job_dir = new_job_dir()
    pdf_path = job_dir / "input.pdf"
    try:
        with pdf_path.open("wb") as f:
            shutil.copyfileobj(file.file, f)

        result = _inspect(pdf_path)
        page_count = getattr(result, "page_count", 0)
        tables_pages = set(getattr(result, "pages_with_tables", []) or [])
        columns_pages = set(getattr(result, "pages_with_columns", []) or [])

        pages = [
            PageLayoutInfo(
                page_index=p - 1,
                has_table=p in tables_pages,
                has_columns=p in columns_pages,
            )
            for p in range(1, page_count + 1)
        ]

        return LayoutDetectResponse(
            filename=file.filename,
            page_count=page_count,
            pdf_type=str(getattr(result, "pdf_type", "unknown")),
            is_complex_layout=bool(getattr(result, "is_complex_layout", False)),
            confidence=float(getattr(result, "confidence", 0.0)),
            pages=pages,
        )
    finally:
        shutil.rmtree(job_dir, ignore_errors=True)


@table_router.post("/detect", response_model=TableDetectResponse)
async def detect_table(file: UploadFile = File(...)):
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(400, "Chi ho tro file .pdf")

    job_dir = new_job_dir()
    pdf_path = job_dir / "input.pdf"
    try:
        with pdf_path.open("wb") as f:
            shutil.copyfileobj(file.file, f)

        result = _inspect(pdf_path)
        page_count = getattr(result, "page_count", 0)
        tables_pages = set(getattr(result, "pages_with_tables", []) or [])

        pages = [
            TableBox(page_index=p - 1, has_table=p in tables_pages)
            for p in range(1, page_count + 1)
        ]

        return TableDetectResponse(
            filename=file.filename,
            page_count=page_count,
            pdf_type=str(getattr(result, "pdf_type", "unknown")),
            pages_with_tables=sorted(tables_pages),
            pages=pages,
        )
    finally:
        shutil.rmtree(job_dir, ignore_errors=True)