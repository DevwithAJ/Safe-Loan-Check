import os

bind = f"0.0.0.0:{os.getenv('PORT', '8000')}"
# One process + threads keeps the built-in low-volume rate limiter consistent.
# For horizontal scaling, replace it with a shared Redis-backed limiter first.
workers = 1
worker_class = "gthread"
threads = int(os.getenv("GUNICORN_THREADS", "4"))
timeout = int(os.getenv("GUNICORN_TIMEOUT", "30"))
graceful_timeout = 20
keepalive = 5
max_requests = 1000
max_requests_jitter = 100
accesslog = "-"
errorlog = "-"
loglevel = os.getenv("LOG_LEVEL", "info")
capture_output = True
