"""
Decode output của recognition model thành text.

Giả định model dùng đầu ra kiểu CTC (rất phổ biến cho text recognition):
output shape (T, num_classes) hoặc (1, T, num_classes) - logits/probabilities
theo từng bước thời gian T, num_classes gồm các ký tự + 1 class "blank".

Bạn cần: 1 file charset.txt liệt kê đúng bộ ký tự mà model dùng, mỗi dòng
1 ký tự, THEO ĐÚNG THỨ TỰ index mà model được train (bắt buộc phải khớp,
nếu không thứ tự sẽ ra ký tự sai hoàn toàn). File này thường có thể tìm
thấy trong tài nguyên đi kèm khi giải mã .onemodel, hoặc phải tự suy ra
bằng cách test.
"""

from pathlib import Path

import numpy as np


class CtcDecoder:
    def __init__(self, charset_path: Path, blank_index: int = 0):
        self.charset = self._load_charset(charset_path)
        self.blank_index = blank_index

    @staticmethod
    def _load_charset(charset_path: Path) -> list[str]:
        if not charset_path.exists():
            raise FileNotFoundError(
                f"Khong tim thay charset tai {charset_path}. "
                "Ban can tu tao file nay dua tren bo ky tu model duoc train."
            )
        with charset_path.open("r", encoding="utf-8") as f:
            return [line.rstrip("\n") for line in f]

    def decode(self, logits: np.ndarray) -> tuple[str, float]:
        """logits: (T, num_classes). Trả (text, avg_confidence)."""
        if logits.ndim == 3:
            logits = logits[0]

        probs = self._softmax(logits)
        indices = np.argmax(probs, axis=-1)
        confidences = np.max(probs, axis=-1)

        chars = []
        used_confidences = []
        prev_idx = -1
        for idx, conf in zip(indices, confidences):
            if idx != self.blank_index and idx != prev_idx:
                if 0 <= idx < len(self.charset):
                    chars.append(self.charset[idx])
                    used_confidences.append(conf)
            prev_idx = idx

        text = "".join(chars)
        avg_conf = float(np.mean(used_confidences)) if used_confidences else 0.0
        return text, avg_conf

    @staticmethod
    def _softmax(x: np.ndarray) -> np.ndarray:
        e = np.exp(x - np.max(x, axis=-1, keepdims=True))
        return e / np.sum(e, axis=-1, keepdims=True)
