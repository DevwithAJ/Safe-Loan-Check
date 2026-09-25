FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN groupadd --system app && useradd --system --gid app --create-home app

COPY requirements.txt ./
RUN python -m pip install --upgrade pip && pip install -r requirements.txt

COPY . .
RUN mkdir -p /app/instance && chown -R app:app /app

USER app

# Render supplies PORT (normally 10000). Local fallback stays 8000.
EXPOSE 10000

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
  CMD python -c "import os, urllib.request; urllib.request.urlopen('http://127.0.0.1:%s/readyz' % os.getenv('PORT','8000'), timeout=3).read()" || exit 1

CMD ["gunicorn", "-c", "gunicorn.conf.py", "wsgi:app"]
