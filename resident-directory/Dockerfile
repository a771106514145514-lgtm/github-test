FROM python:3.11-slim

# Tesseract OCR + 繁體中文語言包，圖片與掃描版 PDF 的文字辨識需要
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    tesseract-ocr-chi-tra \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PORT=8000
EXPOSE 8000

# 只用一個 worker process（多 threads 處理併發請求）：
# 掃描工作的進度與資料都寫在同一個 SQLite 檔案，避免多個 process 同時寫入互相鎖住。
CMD gunicorn app:app --bind 0.0.0.0:${PORT} --workers 1 --threads 4 --timeout 180
