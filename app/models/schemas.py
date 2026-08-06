from typing import List, Optional, Union
from pydantic import BaseModel, Field


class Box(BaseModel):
    text: str
    score: float
    bbox: Optional[Union[List[float], List[List[float]]]] = None


class ImagePageResult(BaseModel):
    page_index: Optional[int] = None
    source: Optional[str] = None
    boxes: List[Box] = Field(default_factory=list)
    content: Optional[str] = None


class OcrImageResponse(BaseModel):
    image_name: str
    bbox_format: str
    boxes: List[Box] = Field(default_factory=list)
    content: Optional[str] = None


class OcrPdfResponse(BaseModel):
    filename: str
    bbox_format: str
    page_count: int
    pages: List[ImagePageResult] = Field(default_factory=list)


class PdfFastResponse(BaseModel):
    filename: str
    bbox_format: str
    pdf_type: str
    page_count: int
    pages: List[ImagePageResult] = Field(default_factory=list)


class PageLayoutInfo(BaseModel):
    page_index: int
    has_table: bool
    has_columns: bool


class LayoutDetectResponse(BaseModel):
    filename: str
    page_count: int
    pdf_type: str
    is_complex_layout: bool
    confidence: float
    pages: List[PageLayoutInfo] = Field(default_factory=list)


class TableBox(BaseModel):
    page_index: int
    has_table: bool


class TableDetectResponse(BaseModel):
    filename: str
    page_count: int
    pdf_type: str
    pages_with_tables: List[int]
    pages: List[TableBox] = Field(default_factory=list)