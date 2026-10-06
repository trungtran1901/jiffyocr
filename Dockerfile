# escape=`
FROM python:3.12-windowsservercore-ltsc2022

WORKDIR C:\app

COPY requirements.txt .
RUN python -m pip install --no-cache-dir -r requirements.txt

COPY app .\app

ENV OCR_BACKEND=native
ENV OCR_DATA_DIR=C:\app\ocr_data
ENV OCR_TMP_DIR=C:\app\tmp_jobs

COPY ocr_data .\ocr_data
RUN mkdir tmp_jobs

EXPOSE 8000

CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]