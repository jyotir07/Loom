"""LoomLogHandler — drain `loom` log records into an EventSink.

Each `log_call(...)` attaches a `loom` dict to the LogRecord via the
`extra` kwarg. The handler pulls that dict, stamps a timestamp from
the record's `created` field, and forwards to the sink.

Records without a `loom` payload are ignored — that means unrelated
log lines on the same logger (or upstream tracing) don't pollute
the sink.

Failures inside the sink are swallowed to handler.handleError() so a
broken sink can never crash the call site.
"""

from __future__ import annotations

import logging
from typing import Any

from loom.observability.sink import EventSink


class LoomLogHandler(logging.Handler):
    def __init__(self, sink: EventSink, level: int = logging.NOTSET) -> None:
        super().__init__(level=level)
        self.sink = sink

    def emit(self, record: logging.LogRecord) -> None:
        payload = getattr(record, "loom", None)
        if not isinstance(payload, dict):
            return
        try:
            event = dict(payload)
            event.setdefault("ts", record.created)
            self.sink.write(event)
        except Exception:
            self.handleError(record)
