#!/usr/bin/env sh
set -eu
: "${APP_ENV:=production}"
export APP_ENV
exec gunicorn -c gunicorn.conf.py wsgi:app
