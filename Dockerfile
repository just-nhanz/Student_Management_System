FROM python:3.12-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
EXPOSE 5000

# 1 worker + nhieu thread: bo nho tam (preview import, dem dang nhap) nam trong cung 1 tien trinh
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "1", "--threads", "4", "web_main:app"]