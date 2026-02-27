"""app.tools.azure_openai_tool

Azure OpenAI tool supporting **MSI or API key** authentication.

Pattern (matches your notebook):
  msi = ManagedIdentityCredential(client_id=AZURE_MSI_CLIENT_ID)
  token_provider = get_bearer_token_provider(msi, "https://cognitiveservices.azure.com/.default")
  client = AzureOpenAI(azure_endpoint=..., api_version=..., azure_ad_token_provider=token_provider)

Contract:
- Each method asks the model to return a single JSON object.
- Parsing is strict: we extract the first JSON object from the response text.
"""

from __future__ import annotations
import json
import re
from typing import Any

from openai import AzureOpenAI

from app.auth import get_aoai_client_kwargs


def _extract_json(text: str) -> dict[str, Any]:
    """Extract the first JSON object from model output."""
    if not text:
        raise ValueError("Empty model output")

    m = re.search(r"```json\s*(\{.*?\})\s*```", text, flags=re.DOTALL)
    if m:
        return json.loads(m.group(1))

    m2 = re.search(r"(\{.*\})", text, flags=re.DOTALL)
    if not m2:
        raise ValueError("No JSON object found in model output")
    return json.loads(m2.group(1))


class AzureOpenAITool:
    """LLM client wrapper with strict JSON parsing (MSI)."""

    def __init__(self, endpoint: str, chat_deployment: str, logger):
        self.endpoint = endpoint
        self.chat_deployment = chat_deployment
        self.logger = logger

        self.client = AzureOpenAI(
            api_version="2024-12-01-preview",
            azure_endpoint=self.endpoint,
            **get_aoai_client_kwargs(),
        )

    def _chat(self, system: str, user: str) -> dict[str, Any]:
        resp = self.client.chat.completions.create(
            model=self.chat_deployment,
            messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
            temperature=0.1,
        )
        text = resp.choices[0].message.content or ""
        return _extract_json(text)

    def classify_intent(self, user_text: str, history: list[dict[str, str]]) -> dict[str, Any]:
        system = (
            "You are an intent router for a company_name internal analytics assistant.\n"
            "Return ONLY valid JSON.\n"
            "Allowed intent values: DATA_QA, ANALYTICS_REPORT, GENERAL_QA, OUT_OF_SCOPE.\n"
            'Schema example: {"intent":"DATA_QA","confidence":0.7,"reason":"..."}\n'
        )
        return self._chat(system, f"User message: {user_text}")

    def check_clarity(self, user_text: str, grounding_text: str, history: list[dict[str, str]]) -> dict[str, Any]:
        system = (
            "You decide if the user's request is clear enough to answer with SQL.\n"
            "If ambiguous, ask clarifying questions and suggest options.\n"
            "Return ONLY valid JSON.\n"
            'Schema example: {"is_clear":false,"questions":["..."],"assumptions_if_proceed":["..."]}\n'
        )
        user = f"User message: {user_text}\n\nRelevant metadata:\n{grounding_text[:6000]}"
        return self._chat(system, user)

    def generate_sql(self, user_text: str, grounding_text: str, limits: dict[str, Any], history: list[dict[str, str]]) -> dict[str, Any]:
        system = (
            "You generate read-only SQL for company_name internal analytics.\n"
            "Rules:\n"
            "- SELECT-only. No DDL/DML. No multiple statements. No comments.\n"
            "- Use ONLY tables/columns mentioned in the provided metadata.\n"
            "- Prefer aggregation for large tables.\n"
            "- Respect the limits provided.\n"
            "- Produce BOTH SQL Server and SQLite versions.\n\n"
            "Return ONLY valid JSON with this schema:\n"
            '{"sql_server":"...","sql_sqlite":"...","used_tables":["schema.table"],"notes":"..."}\n'
        )
        user = (
            f"User question: {user_text}\n"
            f"Limits: {json.dumps(limits)}\n\n"
            f"Metadata (grounding):\n{grounding_text[:8000]}"
        )
        return self._chat(system, user)

    def interpret_result(self, user_text: str, sql: str, result_preview: str, history: list[dict[str, str]]) -> dict[str, Any]:
        system = (
            "You are a company_name analytics assistant. Explain the results clearly and concisely.\n"
            "Do not invent facts not supported by the result preview.\n"
            "Return ONLY valid JSON.\n"
            'Schema example: {"answer":"...","followups":["..."]}\n'
        )
        user = f"User question: {user_text}\nSQL executed:\n{sql}\n\nResult preview:\n{result_preview[:12000]}"
        return self._chat(system, user)

    def create_chart_spec(self, user_text: str, result_preview: str, history: list[dict[str, str]]) -> dict[str, Any]:
        system = (
            "You create a chart specification for an analytics report.\n"
            "Choose chart_type among: line, bar, pie, none.\n"
            "Return ONLY valid JSON.\n"
            'Schema example: {"chart_type":"line","x":"day","y":"count","title":"..."}\n'
        )
        user = f"User request: {user_text}\nResult preview:\n{result_preview[:12000]}"
        return self._chat(system, user)

    def triage_error(self, user_text: str, sql: str, error: str, grounding_text: str, history: list[dict[str, str]]) -> dict[str, Any]:
        system = (
            "You triage SQL execution errors for a company_name analytics assistant.\n"
            "Decide whether to retry with a patched query, ask clarification, or stop.\n"
            "Return ONLY valid JSON.\n"
            'Schema example: {"action":"RETRY_WITH_PATCH","patched_sql_server":null,"patched_sql_sqlite":null,"clarifying_questions":[],"user_message":"..."}\n'
        )
        user = (
            f"User question: {user_text}\n\n"
            f"SQL attempted:\n{sql}\n\n"
            f"DB error:\n{error}\n\n"
            f"Metadata:\n{grounding_text[:8000]}"
        )
        return self._chat(system, user)
