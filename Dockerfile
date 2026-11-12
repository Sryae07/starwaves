FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# OCR 为可选能力（体积大、部分镜像构建慢）：构建时显式开启
ARG WITH_OCR=false
RUN if [ "$WITH_OCR" = "true" ]; then pip install --no-cache-dir -r requirements-ocr.txt; fi

COPY . .
RUN mkdir -p /app/data

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
