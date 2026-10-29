#!/bin/bash
set -e

# 1. Start Nginx as a background daemon
nginx

# 2. Define graceful shutdown handler
_term() {
  echo "SIGTERM received, initiating graceful shutdown..."

  # Stop Nginx gracefully (drains active HTTP connections)
  nginx -s quit 2>/dev/null || true

  # Tell Gunicorn to terminate gracefully
  if [ -n "$GUNICORN_PID" ]; then
    kill -QUIT "$GUNICORN_PID" 2>/dev/null || true
    wait "$GUNICORN_PID" 2>/dev/null || true
  fi

  exit 0
}

# Trap termination signals
trap _term SIGTERM SIGINT

# 3. Start Gunicorn in the background so bash can handle traps
poetry run gunicorn -c /peregrine/deployment/wsgi/gunicorn.conf.py &
GUNICORN_PID=$!

# 4. Wait for Gunicorn process to exit
wait "$GUNICORN_PID"
EXIT_CODE=$?

# If Gunicorn crashes unexpectedly on its own, stop Nginx and exit with that code
nginx -s quit 2>/dev/null || true
exit $EXIT_CODE