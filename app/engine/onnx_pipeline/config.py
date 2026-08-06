import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent

# Thư mục chứa các file .onnx ĐÃ GIẢI MÃ (bạn tự trích bằng tool có sẵn,
# repo này không thực hiện việc giải mã .onemodel).
ONNX_MODELS_DIR = Path(os.environ.get("ONNX_MODELS_DIR", BASE_DIR / "onnx_models"))

# Tên file model kỳ vọng trong ONNX_MODELS_DIR - SỬA LẠI cho khớp với tên
# thật sau khi bạn giải mã xong (34 file), đây chỉ là ví dụ vai trò từng model.
DETECTION_MODEL = ONNX_MODELS_DIR / "detection.onnx"       # phát hiện vùng chữ (heatmap/segment)
RECOGNITION_MODEL = ONNX_MODELS_DIR / "recognition.onnx"    # nhận dạng text trong 1 dòng đã crop

# Kích thước resize đầu vào cho detection model - PHẢI khớp shape thật của
# model (xem bằng `onnx.load(...).graph.input` hoặc netron.app).
DETECTION_INPUT_SIZE = (960, 960)  # (width, height) - placeholder, cần kiểm tra lại

# Chiều cao chuẩn hoá khi crop 1 dòng chữ trước khi đưa vào recognition model
RECOGNITION_INPUT_HEIGHT = 32  # placeholder, cần kiểm tra lại

# Ngưỡng lọc theo confidence (theo tài liệu công khai, oneocr.dll dùng ~0.8)
TEXT_CONFIDENCE_THRESHOLD = float(os.environ.get("TEXT_CONFIDENCE_THRESHOLD", "0.8"))

# Ngưỡng IoU cho các tầng NMS
NMS_IOU_THRESHOLD = float(os.environ.get("NMS_IOU_THRESHOLD", "0.3"))

# onnxruntime execution providers - mac dinh CPU, doi sang CUDAExecutionProvider
# neu co GPU + cai onnxruntime-gpu
ORT_PROVIDERS = os.environ.get("ORT_PROVIDERS", "CPUExecutionProvider").split(",")
