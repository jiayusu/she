FROM python:3.12-slim
WORKDIR /app/agents/interaction
RUN pip install --no-cache-dir flask==3.1.2 gunicorn==23.0.0 PyYAML==6.0.2
COPY agents/interaction/src ./src
COPY agents/interaction/server.py ./server.py
ENV PYTHONPATH=/app/agents/interaction/src
RUN useradd --uid 10001 --create-home she
USER she
HEALTHCHECK --interval=15s --timeout=5s --start-period=10s CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8791/healthz')"
CMD ["gunicorn", "--bind", "0.0.0.0:8791", "--workers", "1", "--threads", "4", "server:app"]
