FROM python:3.11-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app
COPY lending-service/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY shared ./shared
COPY lending-service/ .
EXPOSE 8002
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8002"]
