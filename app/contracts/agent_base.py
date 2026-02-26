"""app.contracts.agent_base

Base abstractions for agents and shared chat context.
"""

from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Generic, TypeVar, Optional, Any

from .models import ChatRequest, Intent, GroundingPack, SqlPlan, SafetyReport, QueryResult, ChartSpec

T = TypeVar("T")


@dataclass
class ChatContext:
    """Shared context passed across the pipeline."""
    request: ChatRequest
    intent: Optional[Intent] = None
    grounding: Optional[GroundingPack] = None
    sql_plan: Optional[SqlPlan] = None
    safety: Optional[SafetyReport] = None
    query_result: Optional[QueryResult] = None
    chart_spec: Optional[ChartSpec] = None
    last_error: Optional[str] = None


class BaseAgent(ABC, Generic[T]):
    """Abstract agent interface."""

    name: str

    @abstractmethod
    def run(self, ctx: ChatContext) -> T:
        """Run this agent step and return a typed result."""
        raise NotImplementedError
