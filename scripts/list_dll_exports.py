"""
Tiện ích: liệt kê các hàm được export bởi oneocr.dll để đối chiếu / sửa lại
tên hàm & thứ tự tham số dùng trong app/engine/win/ocr_worker.py.

QUAN TRỌNG: Tên hàm (CreateOcrInitOptions, RunOcrPipeline, GetOcrLineText...)
trong ocr_worker.py là suy ra theo quy ước đặt tên phổ biến của các API OCR
kiểu này (Windows.Media.Ocr) và có thể KHÔNG khớp 100% với DLL bạn có (Snipping
Tool đã cập nhật nhiều lần, export có thể đổi tên/tham số). Trước khi build
Docker, hãy chạy script này trên máy Windows (Python thường, không cần Wine)
để lấy danh sách export thật, rồi sửa lại ocr_worker.py cho khớp.

Chạy trên Windows:
    pip install pefile
    python list_dll_exports.py C:\\path\\to\\oneocr.dll
"""

import sys

try:
    import pefile
except ImportError:
    print("Cai dat truoc: pip install pefile")
    sys.exit(1)


def main():
    if len(sys.argv) != 2:
        print("Dung: python list_dll_exports.py <duong_dan_toi_oneocr.dll>")
        sys.exit(1)

    pe = pefile.PE(sys.argv[1])
    if not hasattr(pe, "DIRECTORY_ENTRY_EXPORT"):
        print("DLL nay khong co bang export (co the bi strip).")
        return

    print(f"Tim thay {len(pe.DIRECTORY_ENTRY_EXPORT.symbols)} ham export:\n")
    for sym in pe.DIRECTORY_ENTRY_EXPORT.symbols:
        name = sym.name.decode() if sym.name else f"ordinal_{sym.ordinal}"
        print(f"  [{sym.ordinal:>4}]  {name}")


if __name__ == "__main__":
    main()
