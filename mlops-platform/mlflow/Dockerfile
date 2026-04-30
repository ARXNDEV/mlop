FROM ghcr.io/mlflow/mlflow:v2.11.1
RUN (apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*) || (apk add --no-cache curl)
RUN pip install --no-cache-dir psycopg2-binary==2.9.9
