FROM python:3.12-slim

WORKDIR /app

# System deps for matplotlib
RUN apt-get update && apt-get install -y --no-install-recommends \
    libfreetype6-dev libpng-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ ./src/

# Default command runs the API. Override in docker-compose / k8s for the worker.
ENV PYTHONPATH=/app
EXPOSE 5000
CMD ["uvicorn", "src.api:app", "--host", "0.0.0.0", "--port", "5000"]
