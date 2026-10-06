import ctypes
import json
import os
import sys
from ctypes import (
    POINTER,
    Structure,
    byref,
    c_char,
    c_char_p,
    c_float,
    c_int32,
    c_int64,
    c_ubyte,
)

MODEL_KEY = b"kj)TGtrK>f]b[Piow.gU+nC@s\"\"\"\"\"\"4"

c_int64_p = POINTER(c_int64)
c_float_p = POINTER(c_float)
c_ubyte_p = POINTER(c_ubyte)


class OcrImage(Structure):
    _fields_ = [
        ("type", c_int32),
        ("width", c_int32),
        ("height", c_int32),
        ("_reserved", c_int32),
        ("step_size", c_int64),
        ("data_ptr", c_ubyte_p),
    ]


class OcrBoundingBox(Structure):
    _fields_ = [
        ("x1", c_float), ("y1", c_float),
        ("x2", c_float), ("y2", c_float),
        ("x3", c_float), ("y3", c_float),
        ("x4", c_float), ("y4", c_float),
    ]


OcrBoundingBox_p = POINTER(OcrBoundingBox)

DLL_FUNCTIONS = [
    ("CreateOcrInitOptions", [c_int64_p], c_int64),
    ("OcrInitOptionsSetUseModelDelayLoad", [c_int64, c_char], c_int64),
    ("CreateOcrPipeline", [c_char_p, c_char_p, c_int64, c_int64_p], c_int64),
    ("CreateOcrProcessOptions", [c_int64_p], c_int64),
    ("OcrProcessOptionsSetMaxRecognitionLineCount", [c_int64, c_int64], c_int64),
    ("RunOcrPipeline", [c_int64, POINTER(OcrImage), c_int64, c_int64_p], c_int64),
    ("GetImageAngle", [c_int64, c_float_p], c_int64),
    ("GetOcrLineCount", [c_int64, c_int64_p], c_int64),
    ("GetOcrLine", [c_int64, c_int64, c_int64_p], c_int64),
    ("GetOcrLineContent", [c_int64, POINTER(c_char_p)], c_int64),
    ("GetOcrLineBoundingBox", [c_int64, POINTER(OcrBoundingBox_p)], c_int64),
    ("GetOcrLineWordCount", [c_int64, c_int64_p], c_int64),
    ("GetOcrWord", [c_int64, c_int64, c_int64_p], c_int64),
    ("GetOcrWordContent", [c_int64, POINTER(c_char_p)], c_int64),
    ("GetOcrWordBoundingBox", [c_int64, POINTER(OcrBoundingBox_p)], c_int64),
    ("GetOcrWordConfidence", [c_int64, c_float_p], c_int64),
    ("ReleaseOcrResult", [c_int64], None),
    ("ReleaseOcrInitOptions", [c_int64], None),
    ("ReleaseOcrPipeline", [c_int64], None),
    ("ReleaseOcrProcessOptions", [c_int64], None),
]


def bgra_bytes_from_image_path(image_path):
    from PIL import Image

    img = Image.open(image_path).convert("RGBA")
    r, g, b, a = img.split()
    bgra = Image.merge("RGBA", (b, g, r, a))
    width, height = bgra.size
    return bgra.tobytes(), width, height


class OneOcrEngine:
    def __init__(self, ocr_data_dir):
        self.ocr_data_dir = os.path.abspath(ocr_data_dir)
        self.dll_path = os.path.join(self.ocr_data_dir, "oneocr.dll")
        self.model_path = os.path.join(self.ocr_data_dir, "oneocr.onemodel")
        self.onnxruntime_path = os.path.join(self.ocr_data_dir, "onnxruntime.dll")

        if not os.path.exists(self.dll_path):
            raise FileNotFoundError(f"Khong thay oneocr.dll tai {self.dll_path}")
        if not os.path.exists(self.model_path):
            raise FileNotFoundError(f"Khong thay oneocr.onemodel tai {self.model_path}")
        if not os.path.exists(self.onnxruntime_path):
            raise FileNotFoundError(f"Khong thay onnxruntime.dll tai {self.onnxruntime_path}")

        os.environ["PATH"] = self.ocr_data_dir + os.pathsep + os.environ.get("PATH", "")

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.SetDllDirectoryW.argtypes = [ctypes.c_wchar_p]
        kernel32.SetDllDirectoryW.restype = ctypes.c_int
        if not kernel32.SetDllDirectoryW(self.ocr_data_dir):
            raise RuntimeError(f"SetDllDirectoryW that bai, ma loi {ctypes.get_last_error()}")

        try:
            self._ort_dll = ctypes.WinDLL(self.onnxruntime_path)
        except OSError as exc:
            raise RuntimeError(f"Khong load duoc onnxruntime.dll: {exc}") from exc

        try:
            self.dll = ctypes.WinDLL(self.dll_path)
        except OSError as exc:
            raise RuntimeError(f"Khong load duoc oneocr.dll: {exc}") from exc

        self._bind_functions()

        self.init_options = c_int64()
        self._check(self.dll.CreateOcrInitOptions(byref(self.init_options)), "CreateOcrInitOptions")
        self._check(
            self.dll.OcrInitOptionsSetUseModelDelayLoad(self.init_options, 0),
            "OcrInitOptionsSetUseModelDelayLoad",
        )

        model_buf = ctypes.create_string_buffer(self.model_path.encode("utf-8"))
        key_buf = ctypes.create_string_buffer(MODEL_KEY)
        self.pipeline = c_int64()
        self._check(
            self.dll.CreateOcrPipeline(model_buf, key_buf, self.init_options, byref(self.pipeline)),
            "CreateOcrPipeline",
        )

        self.process_options = c_int64()
        self._check(self.dll.CreateOcrProcessOptions(byref(self.process_options)), "CreateOcrProcessOptions")
        self._check(
            self.dll.OcrProcessOptionsSetMaxRecognitionLineCount(self.process_options, 1000),
            "OcrProcessOptionsSetMaxRecognitionLineCount",
        )

    def _bind_functions(self):
        for name, argtypes, restype in DLL_FUNCTIONS:
            func = getattr(self.dll, name)
            func.argtypes = argtypes
            func.restype = restype

    @staticmethod
    def _check(rc, step_name):
        if rc != 0:
            raise RuntimeError(f"{step_name} that bai, ma loi {rc}")

    def _read_text(self, handle, get_content_func):
        content = c_char_p()
        if get_content_func(handle, byref(content)) != 0 or not content.value:
            return ""
        return content.value.decode("utf-8", errors="replace")

    def _read_bbox(self, handle, get_bbox_func):
        bbox_ptr = OcrBoundingBox_p()
        if get_bbox_func(handle, byref(bbox_ptr)) != 0 or not bbox_ptr:
            return None
        b = bbox_ptr.contents
        return {
            "x1": b.x1, "y1": b.y1, "x2": b.x2, "y2": b.y2,
            "x3": b.x3, "y3": b.y3, "x4": b.x4, "y4": b.y4,
        }

    def _line_confidence(self, line_handle):
        word_count = c_int64()
        if self.dll.GetOcrLineWordCount(line_handle, byref(word_count)) != 0:
            return 0.0

        confidences = []
        for i in range(word_count.value):
            word_handle = c_int64()
            if self.dll.GetOcrWord(line_handle, i, byref(word_handle)) != 0:
                continue
            conf = c_float()
            if self.dll.GetOcrWordConfidence(word_handle, byref(conf)) == 0:
                confidences.append(conf.value)

        return sum(confidences) / len(confidences) if confidences else 0.0

    def run(self, image_path):
        bgra_bytes, width, height = bgra_bytes_from_image_path(image_path)
        buf = (c_ubyte * len(bgra_bytes)).from_buffer_copy(bgra_bytes)

        image = OcrImage(
            type=3,
            width=width,
            height=height,
            _reserved=0,
            step_size=width * 4,
            data_ptr=ctypes.cast(buf, c_ubyte_p),
        )

        result_handle = c_int64()
        rc = self.dll.RunOcrPipeline(self.pipeline, byref(image), self.process_options, byref(result_handle))
        if rc != 0:
            raise RuntimeError(f"RunOcrPipeline that bai, ma loi {rc}")

        try:
            line_count = c_int64()
            self._check(self.dll.GetOcrLineCount(result_handle, byref(line_count)), "GetOcrLineCount")

            lines = []
            text_parts = []
            for i in range(line_count.value):
                line_handle = c_int64()
                if self.dll.GetOcrLine(result_handle, i, byref(line_handle)) != 0:
                    continue

                text = self._read_text(line_handle, self.dll.GetOcrLineContent)
                bbox = self._read_bbox(line_handle, self.dll.GetOcrLineBoundingBox)

                lines.append({
                    "text": text,
                    "bbox": bbox,
                    "confidence": self._line_confidence(line_handle),
                })
                text_parts.append(text)

            angle = c_float()
            has_angle = self.dll.GetImageAngle(result_handle, byref(angle)) == 0

            return {
                "width": width,
                "height": height,
                "text": "\n".join(text_parts),
                "lines": lines,
                "text_angle": angle.value if has_angle else None,
            }
        finally:
            self.dll.ReleaseOcrResult(result_handle)


def main():
    if len(sys.argv) != 3:
        print(json.dumps({"ok": False, "error": "usage: ocr_worker.py <ocr_data_dir> <image_path>"}))
        sys.exit(1)

    ocr_data_dir, image_path = sys.argv[1], sys.argv[2]
    try:
        engine = OneOcrEngine(ocr_data_dir)
        result = engine.run(image_path)
        print(json.dumps({"ok": True, "result": result}, ensure_ascii=False))
    except Exception as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False))
        sys.exit(1)


if __name__ == "__main__":
    main()