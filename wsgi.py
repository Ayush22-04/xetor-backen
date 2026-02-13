"""WSGI entrypoint for hosting platforms that look for `wsgi.py`.

Exports a module-level `app` (Flask instance) so platforms like Vercel/UWSGI/Gunicorn
can import it directly: `from wsgi import app`.

This simply uses the existing application factory in `app.create_app()`.
"""
from app import create_app

# create and expose the Flask application instance expected by hosts
app = create_app()
