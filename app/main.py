from fastapi import FastAPI

from app.routers import layout, ocr_image, ocr_pdf_fast, ocr_pdf

app = FastAPI(
    title="JiffyOCR API",
    description="OCR API for Vietnamese documents with standard preprocessing pipeline",
    version="0.1.0",
)

app.include_router(ocr_image.router)
app.include_router(ocr_pdf.router)
app.include_router(ocr_pdf_fast.router)
app.include_router(layout.router)
app.include_router(layout.table_router)


@app.get("/health")
async def health():
    return {"status": "ok"}