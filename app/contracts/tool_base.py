"""app.contracts.tool_base

Tool interfaces for external systems.
"""

from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Any


class MetadataSearchTool(ABC):
    @abstractmethod
    def search(self, query: str, top_k: int) -> dict[str, list[dict[str, Any]]]:
        raise NotImplementedError


class LLMTool(ABC):
    @abstractmethod
    def classify_intent(self, user_text: str, history: list[dict[str, str]]) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def check_clarity(self, user_text: str, grounding_text: str, history: list[dict[str, str]]) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def generate_sql(self, user_text: str, grounding_text: str, limits: dict[str, Any], history: list[dict[str, str]]) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def interpret_result(self, user_text: str, sql: str, result_preview: str, history: list[dict[str, str]]) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def create_chart_spec(self, user_text: str, result_preview: str, history: list[dict[str, str]]) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def triage_error(self, user_text: str, sql: str, error: str, grounding_text: str, history: list[dict[str, str]]) -> dict[str, Any]:
        raise NotImplementedError


class DatabaseTool(ABC):
    @abstractmethod
    def execute(self, sql: str, timeout_seconds: int) -> dict[str, Any]:
        raise NotImplementedError
