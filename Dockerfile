FROM python:3.13-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    HOST=0.0.0.0 \
    PORT=8000 \
    DATABASE_PATH=/var/data/igreja.sqlite3 \
    BACKUP_DIR=/var/data/backups

WORKDIR /app
COPY requirements-lock.txt ./
RUN pip install --no-cache-dir -r requirements-lock.txt && pip check
RUN groupadd --gid 10001 app && useradd --uid 10001 --gid app --create-home app \
    && mkdir -p /var/data && chown app:app /var/data
COPY --chown=app:app backend ./backend
COPY --chown=app:app deploy ./deploy
COPY --chown=app:app frontend ./frontend
USER app
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
    CMD python -c "import os,urllib.request; urllib.request.urlopen('http://127.0.0.1:'+os.environ.get('PORT','8000')+'/healthz',timeout=4).close()"
CMD ["python", "-m", "backend.production"]
