FROM python:3.11-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY kalkan/ kalkan/
COPY scripts/ scripts/
# Seed data + first model version are baked into the image; volumes override them in production.
RUN python scripts/build_dataset.py && python scripts/train_classical.py
EXPOSE 8000
HEALTHCHECK --interval=30s CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/ready')"
CMD ["uvicorn", "kalkan.api.app:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
