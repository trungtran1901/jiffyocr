"""
Tiền xử lý ảnh cho pipeline ONNX thuần.

Lưu ý: thông số normalize (mean/std) dưới đây là giá trị phổ biến cho model
OCR dạng này (ImageNet-style) - bạn cần đối chiếu lại với metadata thật của
model (nếu có ghi trong ONNX) hoặc test thử để tinh chỉnh cho khớp kết quả.
"""

import numpy as np
from PIL import Image

# Giá trị mặc định kiểu ImageNet - CẦN kiểm tra lại với model thật
MEAN = np.array([0.485, 0.456, 0.406], dtype=np.float32)
STD = np.array([0.229, 0.224, 0.225], dtype=np.float32)


def load_rgb(image_path) -> np.ndarray:
    img = Image.open(image_path).convert("RGB")
    return np.array(img)  # HWC, uint8


def resize_keep_ratio(img: np.ndarray, target_wh: tuple[int, int]):
    """Resize giữ tỉ lệ, pad thêm cho đủ kích thước target. Trả về ảnh đã
    resize + hệ số scale + offset pad để sau này quy đổi bbox về ảnh gốc."""
    target_w, target_h = target_wh
    h, w = img.shape[:2]
    scale = min(target_w / w, target_h / h)
    new_w, new_h = int(round(w * scale)), int(round(h * scale))

    resized = np.array(Image.fromarray(img).resize((new_w, new_h), Image.BILINEAR))

    canvas = np.zeros((target_h, target_w, 3), dtype=np.uint8)
    pad_x = (target_w - new_w) // 2
    pad_y = (target_h - new_h) // 2
    canvas[pad_y:pad_y + new_h, pad_x:pad_x + new_w] = resized

    return canvas, scale, (pad_x, pad_y)


def normalize_for_model(img_uint8: np.ndarray) -> np.ndarray:
    """HWC uint8 -> CHW float32 normalized, thêm batch dim."""
    img = img_uint8.astype(np.float32) / 255.0
    img = (img - MEAN) / STD
    img = img.transpose(2, 0, 1)  # HWC -> CHW
    return np.expand_dims(img, axis=0)  # NCHW


def crop_and_prepare_line(img: np.ndarray, quad, target_height: int) -> np.ndarray:
    """Crop 1 dòng chữ theo bbox (tứ giác 4 điểm), xoay thẳng nếu cần, resize
    về chiều cao chuẩn cho recognition model. Đây là bản đơn giản dùng
    axis-aligned bounding box; nếu text bị nghiêng nhiều, cần warp
    perspective thay vì crop thẳng."""
    xs = [quad["x1"], quad["x2"], quad["x3"], quad["x4"]]
    ys = [quad["y1"], quad["y2"], quad["y3"], quad["y4"]]
    x_min, x_max = max(0, int(min(xs))), int(max(xs))
    y_min, y_max = max(0, int(min(ys))), int(max(ys))

    crop = img[y_min:y_max, x_min:x_max]
    if crop.size == 0:
        return None

    h, w = crop.shape[:2]
    new_w = max(1, int(w * (target_height / h)))
    resized = np.array(Image.fromarray(crop).resize((new_w, target_height), Image.BILINEAR))
    return resized
