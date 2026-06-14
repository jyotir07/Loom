"""Loom observability — event sink + log handler + dashboard.

Every `loom.generate(...)` call already emits a structured log record on
the `loom` logger; `record.loom` carries a dict of provider, model,
latency, tokens, cost, cached/deduped flags. This module gives those
records a home and a face:

    from loom.observability import SQLiteSink, LoomLogHandler, make_dashboard
    import logging

    sink = SQLiteSink("loom_events.db")
    logging.getLogger("loom").addHandler(LoomLogHandler(sink))

    # Mount the read-only dashboard in any Flask app:
    from flask import Flask
    app = Flask(__name__)
    app.register_blueprint(make_dashboard(sink), url_prefix="/loom-admin")

The dashboard is a thin Blueprint — no global state, no auth. Wrap it
in whatever your host app already uses for login.

Sink and handler have no Flask dependency; only `make_dashboard`
imports Flask, and does so lazily.
"""

from loom.observability.handler import LoomLogHandler
from loom.observability.sink import EventSink, SQLiteSink


def make_dashboard(sink: EventSink):
    """Lazy import — Flask is optional, only the dashboard needs it."""
    from loom.observability.dashboard import make_dashboard as _make

    return _make(sink)


__all__ = ["EventSink", "SQLiteSink", "LoomLogHandler", "make_dashboard"]
