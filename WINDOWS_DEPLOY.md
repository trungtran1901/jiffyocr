# Triển khai OneOCR API trên Windows (chạy trực tiếp bằng uvicorn)

Tài liệu này hướng dẫn chạy ứng dụng này trên Windows mà không cần Docker build hay build image.

> Lưu ý: tên package đúng là `uvicorn`, không phải `unicorn`.

## 1. Yêu cầu hệ thống

- Windows 10/11
- Python 3.10 hoặc 3.11
- Git Bash / PowerShell / Command Prompt
- Có sẵn các file OCR runtime của Microsoft:
  - `oneocr.dll`
  - `oneocr.onemodel`
  - `onnxruntime.dll`

Copy 3 file trên vào thư mục:

```text
<project_root>\ocr_data\
```

Ví dụ:

```text
F:\HITC\oneocr_api\oneocr_api\ocr_data\
```

Nếu thiếu các file này, app sẽ báo lỗi `Thieu thu muc OCR_DATA_DIR` hoặc không khởi tạo được engine OCR.

---

## 2. Clone / mở project

Mở PowerShell trong thư mục dự án:

```powershell
cd F:\HITC\oneocr_api\oneocr_api
```

---

## 3. Tạo môi trường ảo Python

```powershell
py -3.10 -m venv venv
.\venv\Scripts\Activate.ps1
```

Nếu PowerShell bị chặn policy, chạy:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\venv\Scripts\Activate.ps1
```

---

## 4. Cài đặt dependency

```powershell
python -m pip install --upgrade pip
pip install -r requirements.txt
```

---

## 5. Thiết lập biến môi trường (tùy chọn nhưng nên dùng)

Trong PowerShell:

```powershell
$env:OCR_BACKEND = "native"
$env:OCR_DATA_DIR = "$PWD\ocr_data"
$env:OCR_TMP_DIR = "$PWD\tmp_jobs"
$env:OCR_WORKER_TIMEOUT = "90"
```

Nếu muốn lưu vĩnh viễn cho các lần mở shell khác:

```powershell
[Environment]::SetEnvironmentVariable("OCR_BACKEND", "native", "User")
[Environment]::SetEnvironmentVariable("OCR_DATA_DIR", "$PWD\ocr_data", "User")
[Environment]::SetEnvironmentVariable("OCR_TMP_DIR", "$PWD\tmp_jobs", "User")
[Environment]::SetEnvironmentVariable("OCR_WORKER_TIMEOUT", "90", "User")
```

> Trên Windows, app mặc định sẽ dùng `OCR_BACKEND=native` nếu không khai báo. Đây là chế độ cần thiết để dùng `ctypes.WinDLL` và chạy trực tiếp trên Windows.

---

## 6. Chạy app trực tiếp bằng uvicorn

Từ thư mục gốc dự án:

```powershell
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Hoặc dùng module Python:

```powershell
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Nếu chạy ở chế độ production không cần reload:

```powershell
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

---

## 7. Kiểm tra service

Mở trình duyệt hoặc Postman:

```text
http://localhost:8000/health
```

Kết quả mong đợi:

```json
{"status": "ok"}
```

---

## 8. Các endpoint chính

- `GET /health`
- `POST /ocr/image`
- `POST /ocr/pdf`
- `POST /ocr/pdf_fast`
- `GET /layout`

Cách gọi thử:

```powershell
curl http://localhost:8000/health
```

---

## 9. Dùng app trong môi trường Windows mà không cần build

Không cần chạy Docker, không cần build image, không cần `wine` nếu đang ở Windows native.

Chỉ cần:

1. Tạo venv
2. Cài pip install -r requirements.txt
3. Copy DLL/model vào `ocr_data`
4. Chạy `uvicorn app.main:app --host 0.0.0.0 --port 8000`

---

## 10. Khắc phục sự cố thường gặp

### Lỗi: `Thieu thu muc OCR_DATA_DIR`

Kiểm tra file thật sự có trong thư mục `ocr_data`:

```powershell
Get-ChildItem .\ocr_data
```

### Lỗi: không load được `oneocr.dll`

- Đảm bảo đang chạy trên Windows native
- Kiểm tra `OCR_BACKEND` đang là `native`
- Kiểm tra file DLL đúng phiên bản x64 và nằm trong thư mục `ocr_data`

### Lỗi: `ModuleNotFoundError`

```powershell
pip install -r requirements.txt
```

### Lỗi: port 8000 đã được dùng

Thay port khác:

```powershell
python -m uvicorn app.main:app --host 0.0.0.0 --port 8087
```

---

## 11. Ghi chú về license và runtime

`oneocr.dll` và `oneocr.onemodel` là tài sản Microsoft / bản reverse engineering nội bộ; repo này không phân phối lại các file đó. Bạn cần tự copy theo máy Windows cá nhân của mình.

---

## 12. Command ngắn gọn để chạy nhanh

Nếu chỉ cần chạy ngay:

```powershell
cd F:\HITC\oneocr_api\oneocr_api
.\venv\Scripts\Activate.ps1
$env:OCR_BACKEND = "native"
$env:OCR_DATA_DIR = "$PWD\ocr_data"
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

---

## 13. Dòng lệnh khởi động mẫu cho Windows Task Scheduler / service

```powershell
cd F:\HITC\oneocr_api\oneocr_api
.\venv\Scripts\Activate.ps1
$env:OCR_BACKEND = "native"
$env:OCR_DATA_DIR = "F:\HITC\oneocr_api\oneocr_api\ocr_data"
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

---

Nếu cần, tôi có thể tiếp tục viết thêm file `.bat` hoặc `start_windows.bat` để bạn chỉ cần double-click là chạy server ngay.
