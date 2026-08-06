FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive \
    WINEARCH=win64 \
    WINEPREFIX=/root/.wine \
    WINEDEBUG=-all \
    WIN_PYTHON_DIR=/opt/win-python

# --- Cai Python (Linux, cho FastAPI) + Wine (cho worker goi DLL) ---
RUN dpkg --add-architecture i386 && \
    apt-get update && \
    apt-get install -y --no-install-recommends \
        software-properties-common wget curl unzip gnupg2 ca-certificates \
        python3.12 python3-pip python3-venv \
    && mkdir -pm755 /etc/apt/keyrings \
    && wget -O /etc/apt/keyrings/winehq-archive.key https://dl.winehq.org/wine-builds/winehq.key \
    && wget -NP /etc/apt/sources.list.d/ https://dl.winehq.org/wine-builds/ubuntu/dists/noble/winehq-noble.sources \
    && apt-get update \
    && apt-get install -y --install-recommends winehq-stable \
    && rm -rf /var/lib/apt/lists/*

# --- Khoi tao wine prefix mot lan de tranh khoi tao lai khi container chay ---
RUN wineboot --init && sleep 2 || true

# --- Cai Windows Python embeddable + Pillow duoi wine ---
COPY scripts/setup_wine_python.sh /tmp/setup_wine_python.sh
RUN chmod +x /tmp/setup_wine_python.sh && /tmp/setup_wine_python.sh

# --- Cai dependency Python Linux cho FastAPI ---
WORKDIR /app
COPY requirements.txt .
RUN python3 -m pip install --break-system-packages --no-cache-dir -r requirements.txt

# --- Copy source code ---
COPY app ./app
COPY scripts ./scripts

# oneocr.dll / oneocr.onemodel / onnxruntime.dll duoc nen thang vao image.
# CHI dung image nay noi bo - KHONG push len registry cong khai / chia se
# ra ngoai, vi day la tai san doc quyen cua Microsoft.
COPY ocr_data ./ocr_data
RUN mkdir -p /tmp/oneocr_jobs

EXPOSE 8000

CMD ["python3", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]