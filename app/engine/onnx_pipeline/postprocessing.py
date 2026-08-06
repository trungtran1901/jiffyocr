"""
Hậu xử lý cho detection output.

Đây là phần khó nhất để tái tạo đúng 100% so với oneocr.dll gốc (theo phân
tích công khai, phần hậu xử lý C++ của DLL - multi-stage NMS + gộp dòng -
chiếm phần lớn khác biệt kết quả so với việc chỉ chạy suông ONNX). Bản dưới
đây là một pipeline NMS 2 tầng tương đối chuẩn (không chuyên biệt bằng bản
gốc), bạn nên coi là điểm khởi đầu để tinh chỉnh dần theo dữ liệu thực tế.
"""

import numpy as np


def _iou(box_a, box_b):
    xa1, ya1, xa2, ya2 = box_a
    xb1, yb1, xb2, yb2 = box_b

    inter_x1, inter_y1 = max(xa1, xb1), max(ya1, yb1)
    inter_x2, inter_y2 = min(xa2, xb2), min(ya2, yb2)
    inter_w, inter_h = max(0.0, inter_x2 - inter_x1), max(0.0, inter_y2 - inter_y1)
    inter_area = inter_w * inter_h

    area_a = max(0.0, xa2 - xa1) * max(0.0, ya2 - ya1)
    area_b = max(0.0, xb2 - xb1) * max(0.0, yb2 - yb1)
    union = area_a + area_b - inter_area
    return inter_area / union if union > 0 else 0.0


def nms(boxes: list[dict], iou_threshold: float) -> list[dict]:
    """boxes: list[{"bbox": (x1,y1,x2,y2), "score": float, ...}]"""
    if not boxes:
        return []

    boxes_sorted = sorted(boxes, key=lambda b: b["score"], reverse=True)
    keep = []
    while boxes_sorted:
        current = boxes_sorted.pop(0)
        keep.append(current)
        boxes_sorted = [
            b for b in boxes_sorted
            if _iou(current["bbox"], b["bbox"]) < iou_threshold
        ]
    return keep


def filter_by_confidence(boxes: list[dict], threshold: float) -> list[dict]:
    return [b for b in boxes if b["score"] >= threshold]


def group_segments_into_lines(segments: list[dict], y_overlap_ratio: float = 0.5,
                               x_gap_ratio: float = 1.5) -> list[dict]:
    """Gộp các segment nhỏ (ký tự/cụm ký tự) nằm gần nhau trên cùng 1 hàng
    thành 1 dòng chữ hoàn chỉnh. Heuristic đơn giản dựa trên chồng lấp trục Y
    và khoảng cách trục X - thay thế đơn giản hoá cho "SeglinkGroup" của
    DLL gốc, không đảm bảo xử lý tốt layout phức tạp (nhiều cột, bảng...).
    """
    if not segments:
        return []

    segments = sorted(segments, key=lambda s: (s["bbox"][1], s["bbox"][0]))
    lines = []
    used = [False] * len(segments)

    for i, seg in enumerate(segments):
        if used[i]:
            continue
        used[i] = True
        current_line = [seg]
        x1, y1, x2, y2 = seg["bbox"]

        changed = True
        while changed:
            changed = False
            for j, other in enumerate(segments):
                if used[j]:
                    continue
                ox1, oy1, ox2, oy2 = other["bbox"]

                y_overlap = min(y2, oy2) - max(y1, oy1)
                min_h = min(y2 - y1, oy2 - oy1)
                if min_h <= 0:
                    continue
                y_ok = (y_overlap / min_h) >= y_overlap_ratio

                gap = max(ox1 - x2, x1 - ox2, 0)
                avg_h = ((y2 - y1) + (oy2 - oy1)) / 2
                x_ok = gap <= avg_h * x_gap_ratio

                if y_ok and x_ok:
                    current_line.append(other)
                    used[j] = True
                    x1, y1 = min(x1, ox1), min(y1, oy1)
                    x2, y2 = max(x2, ox2), max(y2, oy2)
                    changed = True

        current_line.sort(key=lambda s: s["bbox"][0])
        avg_score = float(np.mean([s["score"] for s in current_line]))
        lines.append({
            "bbox": (x1, y1, x2, y2),
            "score": avg_score,
            "segments": current_line,
        })

    return lines


def scale_bbox_to_original(bbox, scale: float, pad_xy: tuple[float, float]):
    pad_x, pad_y = pad_xy
    x1, y1, x2, y2 = bbox
    return (
        (x1 - pad_x) / scale,
        (y1 - pad_y) / scale,
        (x2 - pad_x) / scale,
        (y2 - pad_y) / scale,
    )
