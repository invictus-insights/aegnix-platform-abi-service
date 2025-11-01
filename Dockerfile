FROM python:3.11-slim
WORKDIR /app
COPY . .
RUN pip install --no-cache-dir fastapi uvicorn aegnix-core aegnix-abi
CMD ["uvicorn", "abi_service.main:app", "--host", "0.0.0.0", "--port", "8080"]
