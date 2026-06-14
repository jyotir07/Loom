"""Read-only Flask Blueprint that renders aggregates from an EventSink.

Usage:

    from flask import Flask
    from loom.observability import SQLiteSink, make_dashboard

    sink = SQLiteSink("loom_events.db")
    app = Flask(__name__)
    app.register_blueprint(make_dashboard(sink), url_prefix="/loom-admin")

Routes mounted on the blueprint:
    GET /                  HTML dashboard (default window: 24h)
    GET /api/summary       JSON summary
    GET /api/by-provider   JSON per-provider rollup
    GET /api/by-model      JSON top models by cost
    GET /api/recent        JSON recent calls

All endpoints accept `?window=1h|24h|7d|30d|all` (default `24h`).
The blueprint has no auth; wrap it in your host app's existing login.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from loom.observability import queries as _q
from loom.observability.sink import EventSink

_DEFAULT_WINDOW = "24h"
_TEMPLATE_DIR = str(Path(__file__).parent / "templates")


def _window_seconds(value: str | None) -> tuple[str, int | None]:
    key = value or _DEFAULT_WINDOW
    if key not in _q.WINDOWS:
        key = _DEFAULT_WINDOW
    return key, _q.WINDOWS[key]


def make_dashboard(sink: EventSink):
    """Build a Flask Blueprint bound to `sink`. Imports Flask lazily."""
    from flask import Blueprint, jsonify, render_template, request

    bp = Blueprint(
        "loom_dashboard",
        __name__,
        template_folder=_TEMPLATE_DIR,
    )

    @bp.route("/", methods=["GET"])
    def index() -> Any:
        key, seconds = _window_seconds(request.args.get("window"))
        return render_template(
            "dashboard.html",
            window=key,
            windows=list(_q.WINDOWS.keys()),
            summary=_q.summary(sink, window_seconds=seconds),
            providers=_q.by_provider(sink, window_seconds=seconds),
            models=_q.by_model(sink, window_seconds=seconds),
            recent=_q.recent(sink, limit=25),
        )

    @bp.route("/api/summary", methods=["GET"])
    def api_summary() -> Any:
        key, seconds = _window_seconds(request.args.get("window"))
        return jsonify({"window": key, **_q.summary(sink, window_seconds=seconds)})

    @bp.route("/api/by-provider", methods=["GET"])
    def api_by_provider() -> Any:
        key, seconds = _window_seconds(request.args.get("window"))
        return jsonify({"window": key, "providers": _q.by_provider(sink, window_seconds=seconds)})

    @bp.route("/api/by-model", methods=["GET"])
    def api_by_model() -> Any:
        key, seconds = _window_seconds(request.args.get("window"))
        limit = int(request.args.get("limit") or 20)
        return jsonify({
            "window": key,
            "models": _q.by_model(sink, window_seconds=seconds, limit=limit),
        })

    @bp.route("/api/recent", methods=["GET"])
    def api_recent() -> Any:
        limit = int(request.args.get("limit") or 50)
        return jsonify({"events": _q.recent(sink, limit=limit)})

    return bp
