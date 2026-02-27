"""app.autogen_framework

First-class AutoGen agents (AutoGen/AG2) using `autogen.AssistantAgent` and `autogen.UserProxyAgent`.

Design goals:
- Agents are first-class objects with strict JSON contracts.
- Orchestrator remains deterministic and enforces guardrails.
- Agents are always called in **single-turn** mode (max_turns=1) to prevent loops.

MSI:
- Uses Azure OpenAI with Entra auth via `azure_ad_token_provider="DEFAULT"`.
- For user-assigned MSI, set AZURE_MSI_CLIENT_ID. We set AZURE_CLIENT_ID accordingly.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from typing import Any, Dict, Optional

# AutoGen import (TD environments can have multiple packages named similarly).
# We expect the AG2/AutoGen package that supports: AssistantAgent, UserProxyAgent, LLMConfig.
try:
    import autogen  # type: ignore
except ModuleNotFoundError:
    try:
        import ag2 as autogen  # type: ignore
    except ModuleNotFoundError as e:
        raise ModuleNotFoundError(
            "Cannot import 'autogen'.\n"
            "Most common cause: the app is running under a different Python interpreter than the one where you installed packages.\n"
            "Run these in the SAME terminal you start the app:\n"
            "  python -c \"import sys; print(sys.executable)\"\n"
            "  python -c \"import autogen; print('autogen ok')\"\n"
            "Fix (recommended):\n"
            "  python -m pip install -U autogen\n"
            "  python -m streamlit run ui/streamlit_app.py\n"
        ) from e


def _env(name: str, default: str | None = None) -> str:
    v = os.environ.get(name, default)
    if v is None or v.strip() == "":
        raise RuntimeError(f"Missing env var: {name}")
    return v.strip()


def build_llm_config() -> autogen.LLMConfig:
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

    # Auth selection:
    # - If AZURE_OPENAI_API_KEY is set, default to API key (unless AZURE_OPENAI_AUTH_MODE=msi).
    # - Otherwise use MSI via azure_ad_token_provider="DEFAULT".
    auth_mode = os.environ.get("AZURE_OPENAI_AUTH_MODE", "auto").strip().lower()
    api_key = os.environ.get("AZURE_OPENAI_API_KEY", "").strip()

    cfg = {
        "model": deployment,
        "base_url": endpoint,
        "api_type": "azure",
        "api_version": api_version,
        "temperature": 0,
    }

    if auth_mode == "apikey":
        use_key = True
    elif auth_mode == "msi":
        use_key = False
    else:
        use_key = bool(api_key)

    if use_key:
        if not api_key:
            raise RuntimeError("AZURE_OPENAI_AUTH_MODE=apikey but AZURE_OPENAI_API_KEY is missing")
        cfg["api_key"] = api_key
    else:
        cfg["azure_ad_token_provider"] = "DEFAULT"

    return autogen.LLMConfig(cfg)


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

        # Fallback path agents (SQL/RAG pipeline)
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

        # Available-data lane agents
        self.registry_router = autogen.AssistantAgent(
            name="registry_router",
            llm_config=self.llm_config,
            system_message=self._sys_registry_router(),
        )
        self.viz_coder = autogen.AssistantAgent(
            name="viz_coder",
            llm_config=self.llm_config,
            system_message=self._sys_viz_coder(),
        )
        self.executive_writer = autogen.AssistantAgent(
            name="executive_writer",
            llm_config=self.llm_config,
            system_message=self._sys_executive_writer(),
        )

    # ----- system prompts -----
    @staticmethod
    def _sys_intent_router() -> str:
        return (
            "You are an intent router for a company_name internal analytics assistant.\n"
            "Return ONLY valid JSON. No markdown.\n"
            "Allowed intents: DATA_QA, ANALYTICS_REPORT, GENERAL_QA, OUT_OF_SCOPE.\n"
            "Schema: {\"intent\":\"DATA_QA\",\"confidence\":0.7,\"reason\":\"...\"}"
        )

    @staticmethod
    def _sys_requirement_clarity() -> str:
        return (
            "You check whether the user's request is clear enough to answer using SQL.\n"
            "Return ONLY valid JSON. No markdown.\n"
            "If unclear, ask up to 5 clarifying questions and suggest options.\n"
            "Schema: {\"is_clear\":false,\"questions\":[\"...\"],\"assumptions_if_proceed\":[\"...\"]}"
        )

    @staticmethod
    def _sys_sql_generator() -> str:
        return (
            "You generate READ-ONLY SQL for company_name internal analytics.\n"
            "Return ONLY valid JSON. No markdown.\n"
            "Rules: SELECT-only. No DDL/DML. No comments. No multiple statements.\n"
            "Use ONLY tables/columns in the provided metadata grounding.\n"
            "Output BOTH SQL Server and SQLite queries.\n"
            "Schema: {\"sql_server\":\"...\",\"sql_sqlite\":\"...\",\"used_tables\":[\"...\"],\"notes\":\"...\"}"
        )

    @staticmethod
    def _sys_error_triage() -> str:
        return (
            "You triage SQL execution errors.\n"
            "Return ONLY valid JSON. No markdown.\n"
            "Actions: RETRY_WITH_PATCH, ASK_CLARIFICATION, STOP\n"
            "Schema: {\"action\":\"STOP\",\"patched_sql_server\":null,\"patched_sql_sqlite\":null,"
            "\"clarifying_questions\":[\"...\"],\"user_message\":\"...\"}"
        )

    @staticmethod
    def _sys_report_planner() -> str:
        return (
            "You create an analytics report plan.\n"
            "Return ONLY valid JSON.\n"
            "Create up to 5 READ-ONLY queries and chart hints.\n"
            "Prefer plotly charts.\n"
        )

    @staticmethod
    def _sys_report_writer() -> str:
        return (
            "You write a report in markdown.\n"
            "Return ONLY valid JSON with schema: {\"markdown\":\"...\",\"followups\":[\"...\"]}.\n"
        )

    @staticmethod
    def _sys_registry_router() -> str:
        return (
            "You map a user question to the best intent key from a provided registry.\n"
            "Return ONLY valid JSON. No markdown.\n"
            "Input is a JSON string: {role, question, intent_keys, built_in_questions}.\n"
            "Output: {\"intent_key\":\"<key>|NONE\",\"confidence\":0-1,\"reason\":\"...\"}.\n"
            "If none fits, return intent_key='NONE'."
        )

    @staticmethod
    def _sys_viz_coder() -> str:
        return (
            "You are a visualization agent for company_name reporting.\n"
            "Return ONLY valid JSON. No markdown.\n"
            "Input is a JSON string with: user_request, table(columns, rows), constraints.\n"
            "Choose the most suitable chart type.\n"
            "If lat and lon are present and the user asks about geography, prefer a map.\n\n"
            "Code rules (MUST FOLLOW):\n"
            "- Do NOT import anything.\n"
            "- Use only pre-provided variables: df, px, go, sns, plt.\n"
            "- Assign final chart to variable `fig`.\n"
            "- No file or network access.\n\n"
            "Output schema: {"
            "\"library\":\"plotly|seaborn|none\","
            "\"chart_type\":\"line|bar|scatter|hist|box|heatmap|pie|map|table|none\","
            "\"title\":\"...\","
            "\"code\":\"...\","
            "\"description\":\"...\","
            "\"alt_text\":\"...\""
            "}"
        )

    @staticmethod
    def _sys_executive_writer() -> str:
        return (
            "You write an executive-ready report in markdown for company_name managers.\n"
            "Return ONLY valid JSON.\n"
            "Input is a JSON string containing: role, question, dataset, key_numbers, observations, chart_descriptions.\n"
            "Write these sections:\n"
            "1) Headline\n"
            "2) Key data points (bullets)\n"
            "3) Risks and opportunities (bullets)\n"
            "4) Decision point (one action)\n"
            "Do not invent numbers not provided.\n"
            "Schema: {\"markdown\":\"...\",\"followups\":[\"...\"]}"
        )

    # ----- call helper -----
    def call_json(self, agent: autogen.AssistantAgent, payload: Any) -> AgentCallResult:
        """Call an agent once (max_turns=1) and parse JSON."""
        if isinstance(payload, (dict, list)):
            message = json.dumps(payload, ensure_ascii=False, default=str)
        elif payload is None:
            message = ""
        else:
            message = str(payload)

        if not message.strip():
            raise ValueError("call_json received an empty payload after normalization")

        self.user_proxy.initiate_chat(agent, message=message, max_turns=1)

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
