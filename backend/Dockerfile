FROM python:3.12-slim

WORKDIR /app

# WeasyPrint (used from Phase 5 to render resume PDFs) links against these at import
# time, not render time — so a missing package fails loudly on startup rather than
# silently much later. Pango pulls cairo, harfbuzz and glib transitively.
RUN apt-get update && apt-get install -y --no-install-recommends \
      libpango-1.0-0 \
      libpangoft2-1.0-0 \
      shared-mime-info \
      fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

HEALTHCHECK --interval=10s --timeout=3s --start-period=5s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/')" || exit 1

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
