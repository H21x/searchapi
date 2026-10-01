"""WSGI entry point for AlwaysData (and any WSGI-only host).

AlwaysData's Python site type serves a WSGI callable named ``application``.
FastAPI is ASGI, so we adapt it with a2wsgi. Each request runs the ASGI app
in its own event loop on a worker thread — the engine itself is synchronous,
so nothing changes behaviourally.
"""
from a2wsgi import ASGIMiddleware

from api import app

application = ASGIMiddleware(app)
