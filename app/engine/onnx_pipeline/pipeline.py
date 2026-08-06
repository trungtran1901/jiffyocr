"""
Pipeline OCR thuần ONNX (khong Wine, khong goi oneocr.dll luc runtime).

Yêu cầu đầu vào (bạn tự chuẩn bị, xem README):
  - onnx_models/detection.onnx     (đã giải mã)
  - onnx_models/recognition.onnx   (đã giải mã)
  - onnx_models/charset.txt        (bộ ký tự đúng thứ tự index của model)

Vì tôi không có quyền truy cập vào các model đã giải mã thật (input/output
shape, tiền xử lý chính xác, hậu xử lý gốc), phần parse_detection_output()
dưới đây dùng MỘT GIẢ ĐỊNH PHỔ BIẾN (heatmap + box regression kiểu
DB/EAST-style) và cần bạn đối chiếu/sửa lại theo output thật của model
(dùng netron.app để xem shape/tên output rồi chỉnh parse_detection_output).
"""

from pathlib import Path

import numpy as np

from app.engine.onnx_pipeline import config
from app.engine.onnx_pipeline.decoder import CtcDecoder
from app.engine.onnx_pipeline.inference import OnnxModel
from app.engine.onnx_pipeline.postprocessing import (
    filter_by_confidence,
    group_segments_into_lines,
    nms,
    scale_bbox_to_original,
)
from app.engine.onnx_pipeline.preprocessing import (
    crop_and_prepare_line,
    load_rgb,
    normalize_for_model,
    resize_keep_ratio,
)


def parse_detection_output(outputs: dict, orig_scale: float, pad_xy: tuple[float, float],
                            threshold: float) -> list[dict]:
    """CẦN SỬA LẠI theo output thật của detection.onnx.

    Giả định tạm thời: output có 1 tensor "boxes" shape (N, 5) = (x1,y1,x2,y2,score)
    ở toạ độ ảnh đã resize (960x960 hoặc theo config.DETECTION_INPUT_SIZE).
    Nếu model thật xuất ra heatmap (segmentation mask) thay vì box trực tiếp,
    cần thêm bước decode heatmap -> box (contour finding, connected components)
    trước khi tới bước NMS.
    """
    boxes_key = next((k for k in outputs if "box" in k.lower()), None)
    if boxes_key is None:
        raise RuntimeError(
            f"Khong tim thay output dang boxes trong {list(outputs.keys())}. "
            "Can tu viet lai parse_detection_output() theo dung output cua model."
        )

    raw = outputs[boxes_key]
    if raw.ndim == 3:
        raw = raw[0]

    segments = []
    for row in raw:
        x1, y1, x2, y2, score = row[:5]
        if score < threshold:
            continue
        bbox = scale_bbox_to_original((x1, y1, x2, y2), orig_scale, pad_xy)
        segments.append({"bbox": bbox, "score": float(score)})

    return segments


class OnnxOcrPipeline:
    def __init__(self, models_dir: Path = None):
        models_dir = models_dir or config.ONNX_MODELS_DIR
        self.detection = OnnxModel(models_dir / config.DETECTION_MODEL.name)
        self.recognition = OnnxModel(models_dir / config.RECOGNITION_MODEL.name)
        self.decoder = CtcDecoder(models_dir / "charset.txt")

    def run(self, image_path) -> dict:
        img = load_rgb(image_path)
        h, w = img.shape[:2]

        resized, scale, pad_xy = resize_keep_ratio(img, config.DETECTION_INPUT_SIZE)
        det_input = normalize_for_model(resized)
        det_outputs = self.detection.run(det_input)

        segments = parse_detection_output(
            det_outputs, scale, pad_xy, config.TEXT_CONFIDENCE_THRESHOLD
        )
        segments = filter_by_confidence(segments, config.TEXT_CONFIDENCE_THRESHOLD)
        segments = nms(segments, config.NMS_IOU_THRESHOLD)
        lines = group_segments_into_lines(segments)

        result_lines = []
        full_text_parts = []
        for line in lines:
            x1, y1, x2, y2 = line["bbox"]
            quad = {"x1": x1, "y1": y1, "x2": x2, "y2": y1, "x3": x2, "y3": y2, "x4": x1, "y4": y2}

            crop = crop_and_prepare_line(img, quad, config.RECOGNITION_INPUT_HEIGHT)
            if crop is None:
                continue

            rec_input = normalize_for_model(crop)
            rec_outputs = self.recognition.run(rec_input)
            logits = next(iter(rec_outputs.values()))
            text, rec_conf = self.decoder.decode(logits)

            if not text:
                continue

            result_lines.append({
                "text": text,
                "confidence": float((line["score"] + rec_conf) / 2),
                "bbox": quad,
                "words": [],
            })
            full_text_parts.append(text)

        return {
            "width": w,
            "height": h,
            "text": "\n".join(full_text_parts),
            "lines": result_lines,
        }


_pipeline_instance = None


def get_pipeline() -> OnnxOcrPipeline:
    global _pipeline_instance
    if _pipeline_instance is None:
        _pipeline_instance = OnnxOcrPipeline()
    return _pipeline_instance
