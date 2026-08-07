# ---------- Stage 1: builder ----------
# Installs dependencies into an isolated location; this whole stage (compilers,
# build tools, pip cache) is discarded and never appears in the final image.
FROM python:3.12-slim AS builder

WORKDIR /build

# gcc is needed to build C extensions some FastAPI/uvicorn dependencies use.
# It stays in this stage only.
RUN apt-get update \
    && apt-get install -y --no-install-recommends gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# ---------- Stage 2: runtime ----------
# Fresh, clean base — no compilers, no pip cache, no apt lists. Only the
# installed Python packages and the application code get copied in.
FROM python:3.12-slim

RUN useradd --create-home --shell /bin/bash appuser

WORKDIR /app

COPY --from=builder --chown=appuser:appuser /root/.local /home/appuser/.local
COPY --chown=appuser:appuser . .

ENV PATH=/home/appuser/.local/bin:$PATH \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Never run the app as root — limits blast radius if the process is compromised.
USER appuser

EXPOSE 8000

# Uses Python's stdlib (urllib) instead of curl/wget so we don't have to
# install extra packages into the final image just for a health probe.
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health', timeout=2)" || exit 1

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
