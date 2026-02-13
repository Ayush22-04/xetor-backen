from flask import Flask
import os
# Do not import the Mongo client at module import time — creating a
# MongoClient can trigger network/DNS resolution during cold-start which
# may crash serverless deployments. The DB client is created lazily by
# `app.extensions.db.get_db()` when a route actually needs DB access.
from app.api.routes import api
from app.admin.routes import admin_bp
from app.extensions.mail import mail as mail_ext
try:
    # optional dependency - only required when enabling cross-origin access
    from flask_cors import CORS
except Exception:
    CORS = None


def create_app():
    app = Flask(__name__)

    # basic secret key for sessions; override with environment variable in production
    app.secret_key = os.getenv("SECRET_KEY", "dev-secret-key-change-me")

    # Enable CORS for the frontend origin if Flask-Cors is installed.
    # This allows requests from http://localhost:8080 (e.g. local frontend dev server).
    if CORS is not None:
        # allow credentials (cookies/session) and restrict to intended origin
        CORS(app, origins=["http://localhost:8080"], supports_credentials=True)
    else:
        # Fallback: add CORS headers manually if Flask-Cors isn't installed or import failed.
        # This helps development setups where package installation differs from requirements.
        @app.after_request
        def _add_cors_headers(response):
            # Allow the frontend dev server origin and credentials.
            response.headers.setdefault("Access-Control-Allow-Origin", "http://localhost:8080")
            response.headers.setdefault("Access-Control-Allow-Credentials", "true")
            # Allow common headers and methods used by the frontend.
            response.headers.setdefault("Access-Control-Allow-Headers", "Content-Type,Authorization")
            response.headers.setdefault("Access-Control-Allow-Methods", "GET,POST,PUT,DELETE,OPTIONS")
            return response

    app.register_blueprint(api, url_prefix="/api")
    app.register_blueprint(admin_bp, url_prefix="/admin")

    # Initialize Flask-Mail extension (reads MAIL_* config from app.config)
    mail_ext.init_app(app)

    return app
