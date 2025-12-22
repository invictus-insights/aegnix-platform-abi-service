#FROM python:3.11-slim
#WORKDIR /app
#COPY . .
#RUN pip install --no-cache-dir fastapi uvicorn aegnix-core aegnix-abi
#CMD ["uvicorn", "abi_service.main:app", "--host", "0.0.0.0", "--port", "8080"]

FROM python:3.11-slim
WORKDIR /app

# Install sqlite3 CLI tool
RUN apt-get update && apt-get install -y sqlite3 && rm -rf /var/lib/apt/lists/*

# Local package directory
RUN mkdir -p /app/local_packages

# Copy wheel files relative to the *build context* (platform/)
COPY aegnix_core/dist/aegnix_core*.whl /app/local_packages/
COPY aegnix_sdk/aegnix_abi_sdk/dist/aegnix_abi*.whl /app/local_packages/
#COPY aegnix_core/dist/*.whl /app/local_packages/
#COPY aegnix_sdk/aegnix_abi_sdk/dist/*.whl /app/local_packages/

# Copy the ABI service code
COPY abi_service/. .

# Install dependencies
RUN pip install --no-cache-dir --find-links=/app/local_packages \
    aegnix-core aegnix-abi fastapi uvicorn sqlite-utils pyJWT  kafka-python

# Start the service
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]






