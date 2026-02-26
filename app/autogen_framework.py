"""app.autogen_framework

First-class AutoGen agents (v0.2 style) using `autogen.AssistantAgent` and `autogen.UserProxyAgent`.

This matches your proven working pattern:
  - llm_config = autogen.LLMConfig({... "azure_ad_token_provider": "DEFAULT" ...})
  - assistant = autogen.AssistantAgent(...)
  - user_proxy.initiate_chat(assistant, ..., max_turns=1)

Guardrails:
- Always single-turn calls (max_turns=1) to prevent loops
- Strict JSON output per agent (orchestration parses/validates)

User-assigned MSI:
- Set AZURE_MSI_CLIENT_ID
- We set AZURE_CLIENT_ID = AZURE_MSI_CLIENT_ID so DefaultAzureCredential selects it
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from typing import Any, Dict, Optional

import autogen


def _env(name: str, default: str | None = None) -> str:
    v = os.environ.get(name, default)
    if v is None or v.strip() == "":
        raise RuntimeError(f"Missing env var: {name}")
    return v.strip()


def build_llm_config() -> autogen.LLMConfig:
    """Build AutoGen LLM config for Azure OpenAI using MSI."""
    endpoint = _env("AZURE_OPENAI_ENDPOINT")
    if not endpoint.endswith("/"):
        endpoint += "/"

    deployment = os.environ.get("AZURE_OPENAI_DEPLOYMENT") or os.environ.get("AZURE_OPENAI_CHAT_DEPLOYMENT")
    if not deployment or not deployment.strip():
        raise RuntimeError("Missing env var: AZURE_OPENAI_DEPLOYMENT (or AZURE_OPENAI_CHAT_DEPLOYMENT)")
    deployment = deployment.strip()

    api_version = os.environ.get("AZURE_OPENAI_API_VERSION", "2024-12-01-preview").strip()

    # Force user-assigned MSI selection for DefaultAzureCredential
    msi_client_id = os.environ.get("AZURE_MSI_CLIENT_ID", "").strip()
    if msi_client_id:
        os.environ["AZURE_CLIENT_ID"] = msi_client_id

    return autogen.LLMConfig(
        {
            "model": deployment,
            "base_url": endpoint,
            "api_type": "azure",
            "api_version": api_version,
            "azure_ad_token_provider": "DEFAULT",
            "temperature": 0,
        }
    )


@dataclass
class AgentCallResult:
    raw_text: str
    json_obj: Optional[Dict[str, Any]]


class AgentManager:
    """Creates and calls first-class AutoGen agents (single-turn)."""

    def __init__(self, logger):
        self.logger = logger
        self.llm_config = build_llm_config()
        self.user_proxy = autogen.UserProxyAgent(
            name="user_proxy",
            human_input_mode="NEVER",
            code_execution_config=False,
        )

        self.intent_router = autogen.AssistantAgent(
            name="intent_router",
            llm_config=self.llm_config,
            system_message=self._sys_intent_router(),
        )
        self.requirement_clarity = autogen.AssistantAgent(
            name="requirement_clarity",
            llm_config=self.llm_config,
            system_message=self._sys_requirement_clarity(),
        )
        self.sql_generator = autogen.AssistantAgent(
            name="sql_generator",
            llm_config=self.llm_config,
            system_message=self._sys_sql_generator(),
        )
        self.error_triage = autogen.AssistantAgent(
            name="error_triage",
            llm_config=self.llm_config,
            system_message=self._sys_error_triage(),
        )
        self.report_planner = autogen.AssistantAgent(
            name="report_planner",
            llm_config=self.llm_config,
            system_message=self._sys_report_planner(),
        )
        self.report_writer = autogen.AssistantAgent(
            name="report_writer",
            llm_config=self.llm_config,
            system_message=self._sys_report_writer(),
        )

    # -------- system prompts (strict JSON) --------
    @staticmethod
    def _sys_intent_router() -> str:
        return (
            "You are an intent router for a company_name internal analytics assistant.\n"
            "Return ONLY valid JSON. No markdown. No code fences.\n"
            "Allowed intents: DATA_QA, ANALYTICS_REPORT, GENERAL_QA, OUT_OF_SCOPE.\n"
            'Schema: {"intent":"DATA_QA","confidence":0.7,"reason":"..."}'
        )

    @staticmethod
    def _sys_requirement_clarity() -> str:
        return (
            "You check whether the user's request is clear enough to answer using SQL.\n"
            "Return ONLY valid JSON. No markdown.\n"
            "If unclear, ask up to 5 clarifying questions and suggest options.\n"
            'Schema: {"is_clear":false,"questions":["..."],"assumptions_if_proceed":["..."]}'
        )

    @staticmethod
    def _sys_sql_generator() -> str:
        return (
            "You generate READ-ONLY SQL for company_name internal analytics.\n"
            "Return ONLY valid JSON. No markdown.\n"
            "Rules:\n"
            "- SELECT-only. No DDL/DML. No comments. No multiple statements.\n"
            "- Use ONLY tables/columns in the provided metadata grounding.\n"
            "- Prefer aggregations when tables may be large.\n"
            "- Output BOTH SQL Server and SQLite queries.\n"
            'Schema: {"sql_server":"...","sql_sqlite":"...","used_tables":["schema.table"],"notes":"..."}'
        )

    @staticmethod
    def _sys_error_triage() -> str:
        return (
            "You triage SQL execution errors.\n"
            "Return ONLY valid JSON. No markdown.\n"
            "Actions: RETRY_WITH_PATCH, ASK_CLARIFICATION, STOP\n"
            'Schema: {"action":"RETRY_WITH_PATCH","patched_sql_server":null,"patched_sql_sqlite":null,'
            '"clarifying_questions":["..."],"user_message":"..."}'
        )

    @staticmethod
    def _sys_report_planner() -> str:
        return (
            "You create an analytics report plan for company_name business users.\n"
            "Return ONLY valid JSON. No markdown.\n"
            "You will be given the user request + metadata grounding.\n"
            "Create up to 5 aggregated READ-ONLY queries (SELECT-only) and chart instructions.\n"
            "Avoid returning raw row-level data; prefer GROUP BY / counts / sums / averages.\n"
            "Chart libraries: prefer plotly (interactive), fallback seaborn.\n"
            "Schema: {"
            '"title":"...","summary":"...","queries":[{'
            '"name":"...","purpose":"...",'
            '"sql_server":"...","sql_sqlite":"...",'
            '"chart":{"library":"plotly|seaborn|none","type":"line|bar|pie|table|none","x":null,"y":null,"title":null}'
            "}],"
            '"followups":["..."]'
            "}"
        )

    @staticmethod
    def _sys_report_writer() -> str:
        return (
            "You write an executive-ready analytics report for company_name business users.\n"
            "Return ONLY valid JSON. No markdown fences.\n"
            "You will receive a report plan and limited query result previews.\n"
            "Output MUST be a single markdown string in the 'markdown' field.\n"
            "Include: headings, bullet points, key numbers, caveats.\n"
            "Do not invent metrics not present in the provided results.\n"
            'Schema: {"markdown":"# Title\\n...","followups":["..."]}'
        )

    def call_json(self, agent: autogen.AssistantAgent, payload: Any) -> AgentCallResult:
        """Call an agent once (max_turns=1) and parse JSON."""
        self.user_proxy.initiate_chat(agent, message=payload, max_turns=1)

        msgs = self.user_proxy.chat_messages.get(agent, [])
        raw = msgs[-1].get("content", "") if msgs else ""

        obj: Optional[Dict[str, Any]] = None
        try:
            obj = json.loads(raw)
        except Exception:
            m = re.search(r"(\{.*\})", raw, flags=re.DOTALL)
            if m:
                try:
                    obj = json.loads(m.group(1))
                except Exception:
                    obj = None

        return AgentCallResult(raw_text=raw, json_obj=obj)
