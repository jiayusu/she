FROM python:3.12-slim
WORKDIR /app/backend/memory_store
RUN pip install --no-cache-dir flask==3.1.2 numpy==2.2.6 requests==2.32.5 gunicorn==23.0.0
COPY backend/memory_store/memstore ./memstore
COPY backend/memory_store/server.py ./server.py
RUN useradd --uid 10001 --create-home she && mkdir /data && chown she:she /data
ENV STORE_DATA=/data USE_FAISS=0 AUTO_JOBS=0 SHE_MEMORY_WSGI=1
USER she
HEALTHCHECK --interval=15s --timeout=5s --start-period=10s CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8789/healthz')"
CMD ["gunicorn", "--bind", "0.0.0.0:8789", "--workers", "1", "--threads", "4", "server:app"]
