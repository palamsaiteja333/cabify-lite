from python:3.12-slim as builder
workdir /app
copy requirements.txt .
run python -m venv /opt/venv
run /opt/venv/bin/pip install --no-cache-dir -r requirements.txt

from python:3.12-slim
workdir /app
run useradd --create-home appuser
copy --from=builder /opt/venv /opt/venv
env PATH="/opt/venv/bin:$PATH"
copy app ./app
user appuser
expose 8000
cmd ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]


