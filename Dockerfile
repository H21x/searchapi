FROM python:3.12-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY websearch.py api.py client.py ./

# Render injects $PORT; default 8000 for local runs
CMD uvicorn api:app --host 0.0.0.0 --port ${PORT:-8000}
