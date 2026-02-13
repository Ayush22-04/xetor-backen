"""Centralized MongoDB client and helper for the Flask app.

Expose:
 - client: a shared MongoClient instance
 - get_db(name='mydatabase'): returns a Database handle
"""
import os
from pymongo import MongoClient
from typing import Optional

# Read URI from environment but do NOT create a network-connected client at
# import time. Some hosting environments (Vercel serverless) disallow or
# restrict outbound network/DNS during cold-start which can cause function
# invocation failures if MongoClient attempts network activity while the
# module is imported.
MONGO_URI = os.getenv(
    "MONGO_URI",
    "mongodb+srv://ayushkamani2004_db_user:KSlVvPAgvm93qjw5@cluster0.1apwudn.mongodb.net/?appName=Cluster0",
)

# Lazily-created MongoClient instance. Use get_db() to obtain a Database
# handle so the client is constructed only when actually needed.
_client: Optional[MongoClient] = None


def _ensure_client() -> MongoClient:
    global _client
    if _client is None:
        # Create client without forcing server selection at import time.
        # serverSelectionTimeoutMS controls how long operations wait for
        # server selection; keep a short timeout to fail fast on unreachable
        # databases during requests.
        _client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
    return _client


def get_db(db_name: str = "xetor"):
    """Return a database handle for the given name (creates client lazily)."""
    client = _ensure_client()
    return client[db_name]
