# OneOCR API (image + PDF)

Bọc `oneocr.dll` (engine OCR của Windows 11 Snipping Tool) thành REST API
bằng FastAPI, chạy trong Docker (Linux) thông qua **Wine**.

## Vì sao cần Wine?

`oneocr.dll` là PE Windows x64, gọi bằng calling convention Windows
(`ctypes.WinDLL`). Trên Linux native, `ctypes.WinDLL` không tồn tại và DLL
không load được. Giải pháp: chạy một **Python Windows embeddable** bên trong
**Wine**, dùng nó để load DLL và chạy OCR. FastAPI (Python Linux, chạy native,
nhanh) chỉ đóng vai trò gọi worker này như một subprocess và nhận kết quả JSON
qua stdout — không cần Wine cho phần server/API, chỉ Wine cho phần gọi DLL.

```
Client
  │  POST /ocr/image  (multipart file)
  │  POST /ocr/pdf     (multipart file)
  ▼
FastAPI (Linux, native, uvicorn)
  │  - PDF: PyMuPDF render mỗi trang -> PNG
  │  - gọi subprocess: wine win-python/python.exe ocr_worker.py <image>
  ▼
ocr_worker.py (chạy dưới Wine, dùng ctypes.WinDLL)
  │  load oneocr.dll + oneocr.onemodel qua onnxruntime.dll
  ▼
Trả JSON {text, lines:[{text, bbox, confidence}]}  qua stdout
```

## Yêu cầu QUAN TRỌNG trước khi build

Bạn phải tự copy 3 file sau (lấy từ máy Windows của bạn, đường dẫn kiểu
`C:\Windows\SystemApps\...SnippingTool...\SnippingTool.Vision.Interop\`)
vào thư mục `ocr_data/` của project này:

- `oneocr.dll`
- `oneocr.onemodel`
- `onnxruntime.dll`

Đây là tài sản của Microsoft đi kèm Windows — repo/image Docker của bạn
**không nên** phân phối lại các file này. Chỉ dùng nội bộ / cho máy cá nhân
của bạn. Xem phần "Lưu ý pháp lý" bên dưới.

## Cấu trúc

```
oneocr_api/
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── ocr_data/                 # <-- bạn tự copy 3 file DLL/model vào đây
├── app/
│   ├── main.py                # FastAPI app
│   ├── config.py
│   ├── routers/
│   │   ├── ocr_image.py
│   │   └── ocr_pdf.py
│   ├── engine/
│   │   ├── worker_bridge.py   # gọi subprocess wine
│   │   └── win/
│   │       └── ocr_worker.py  # chạy dưới Wine, ctypes -> oneocr.dll
│   └── models/
│       └── schemas.py
└── scripts/
    └── setup_wine_python.sh
```

## Lưu ý pháp lý

`oneocr.dll`/`oneocr.onemodel` là tài sản độc quyền của Microsoft, đã bị
reverse engineer bởi cộng đồng (không phải Microsoft public API chính thức).
Dùng nghiên cứu/nội bộ rủi ro thấp; nếu định phân phối công khai hoặc dùng
thương mại, cân nhắc license, hoặc thay thế bằng engine mã nguồn mở
(PaddleOCR, Surya, docTR...).
