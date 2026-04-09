# Dockerfile cho TiniX Story 1.0
# Dựa trên image chính thức của Python 3.11
FROM python:3.11-slim

# Thiết lập thư mục làm việc
WORKDIR /app

# Thiết lập biến môi trường
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

# Cài đặt các dependencies hệ thống
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Sao chép tệp dependencies
COPY requirements.txt .

# Cài đặt dependencies Python
RUN pip install --no-cache-dir -r requirements.txt

# Tạo các thư mục cần thiết
RUN mkdir -p logs data exports projects config

# Sao chép mã nguồn ứng dụng
COPY . .

# Expose ports (FastAPI: 8000, Gradio: 7860)
EXPOSE 8000 7860

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Lệnh khởi động
CMD ["python", "run.py"]