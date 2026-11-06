FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY backend/requirements.lock.txt backend/requirements.lock.txt
RUN pip install --no-cache-dir -r backend/requirements.lock.txt
COPY . .
# Build deterministic artifacts without reaching the deployment database.
RUN DATABASE_URL=sqlite:////tmp/returnwise-build.db python -m scripts.bootstrap
EXPOSE 8000
CMD ["python", "-m", "scripts.start_backend"]
