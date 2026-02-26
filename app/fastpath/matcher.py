"""app.fastpath.matcher

Matches a user question to a QueryTemplate using a dependency-light heuristic.
"""

from __future__ import annotations
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Optional

from .query_registry import QueryTemplate


@dataclass
class MatchResult:
    template: QueryTemplate
    score: float


def score_template(question: str, tmpl: QueryTemplate) -> float:
    q = question.lower()
    kw_hits = sum(1 for k in tmpl.keywords if k.lower() in q)
    kw_score = kw_hits / max(len(tmpl.keywords), 1)
    sim = SequenceMatcher(None, q, (tmpl.name + " " + tmpl.description).lower()).ratio()
    return 0.7 * kw_score + 0.3 * sim


def best_match(question: str, templates: list[QueryTemplate], threshold: float = 0.72) -> Optional[MatchResult]:
    best: Optional[MatchResult] = None
    for t in templates:
        s = score_template(question, t)
        if best is None or s > best.score:
            best = MatchResult(template=t, score=s)
    if best and best.score >= threshold:
        return best
    return None
