"""app.tracing

Trace collection for debug mode.
Each pipeline step appends a structured payload; the UI renders it inline in debug mode.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any


@dataclass
class TraceCollector:
    """Collects per-step traces for a single chat turn."""
    traces: list[dict[str, Any]] = field(default_factory=list)

    def add(self, step_name: str, payload: dict[str, Any]) -> None:
        self.traces.append({"step": step_name, "payload": payload})
