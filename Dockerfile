FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app
ENV NOVEL_TOOL_PORT=7860
ENV NOVEL_TOOL_HOST=0.0.0.0

RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

RUN mkdir -p logs cache output data backups templates project_templates plugins

COPY . .

EXPOSE 7860

HEALTHCHECK --interval=30s --timeout=15s --start-period=90s --retries=5 \
    CMD curl -f http://localhost:7860/ || exit 1

CMD ["python", "app.py"]
