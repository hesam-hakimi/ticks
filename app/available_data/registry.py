"""app.available_data.registry

Loads built-in questions and intent registry from repo `data/`.

Files (preferred):
  - data/intent_registry.json
  - data/built_in_questions.json

These are demo-friendly and can be swapped later.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.paths import data_dir


@dataclass(frozen=True)
class BuiltInQuestion:
    id: str
    text: str
    roles: list[str]
    intent: str


class IntentRegistry:
    def __init__(self, intents: Dict[str, Any]):
        self.intents = intents

    def get(self, key: str) -> Optional[Dict[str, Any]]:
        return self.intents.get(key)

    def keys(self) -> list[str]:
        return list(self.intents.keys())


def load_intent_registry(path: Optional[str] = None) -> IntentRegistry:
    p = Path(path) if path else (data_dir() / "intent_registry.json")
    obj = json.loads(p.read_text(encoding="utf-8"))
    return IntentRegistry(obj.get("intents", {}))


def load_built_in_questions(path: Optional[str] = None) -> list[BuiltInQuestion]:
    p = Path(path) if path else (data_dir() / "built_in_questions.json")
    obj = json.loads(p.read_text(encoding="utf-8"))
    out: list[BuiltInQuestion] = []
    for q in obj.get("questions", []):
        out.append(
            BuiltInQuestion(
                id=str(q.get("id")),
                text=str(q.get("text")),
                roles=list(q.get("roles", [])),
                intent=str(q.get("intent")),
            )
        )
    return out
