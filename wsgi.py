"""WSGI entrypoint for production servers (Gunicorn/Render).

Usage (Render start command):
  gunicorn wsgi:app --bind 0.0.0.0:$PORT --workers 1 --threads 2
"""

from app import create_app

app = create_app()
