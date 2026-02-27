"""app.main

Wiring for tools + policies + agents + orchestrator.

Two-lane design:
- Primary: "currently available" in-memory datasets (fast)
- Fallback: existing metadata + SQL pipeline (only when user confirms)
"""

from __future__ import annotations

import os

from app.env_loader import load_env
from app.config import Settings
from app.logging_utils import build_logger
from app.tracing import TraceCollector

from app.orchestrator import Orchestrator
from app.orchestrator_fallback import FallbackOrchestrator

from app.policy.sql_policy import SqlPolicy
from app.policy.limits_policy import LimitsPolicy

from app.tools.azure_search_tool import AzureAISearchTool
from app.tools.azure_openai_tool import AzureOpenAITool
from app.tools.db_sqlserver_tool import SqlServerDatabaseTool
from app.tools.db_sqlite_tool import SqliteDatabaseTool

from app.agents.metadata_retriever import MetadataRetrieverAgent
from app.agents.sql_safety_guard import SQLSafetyGuardAgent
from app.agents.db_executor import DBExecutorAgent

from app.autogen_framework import AgentManager


def build_orchestrator() -> Orchestrator:
    load_env()  # load .env if present
    settings = Settings.load()
    logger = build_logger(settings.log_dir)
    tracer = TraceCollector()

    # Tools for fallback path
    search_tool = AzureAISearchTool(
        endpoint=settings.azure_search_endpoint,
        index_field=settings.index_field,
        index_table=settings.index_table,
        index_relationship=settings.index_relationship,
        logger=logger,
    )
    llm_tool = AzureOpenAITool(
        endpoint=settings.azure_openai_endpoint,
        chat_deployment=settings.azure_openai_chat_deployment,
        logger=logger,
    )

    if settings.db_backend == "sqlite":
        db_tool = SqliteDatabaseTool(settings.sqlite_path, logger=logger)
    else:
        db_tool = SqlServerDatabaseTool(
            server=settings.azure_sql_server,
            database=settings.azure_sql_database,
            conn_str=settings.azure_sql_conn_str,
            logger=logger,
        )

    sql_policy = SqlPolicy()
    limits_policy = LimitsPolicy()

    metadata_retriever = MetadataRetrieverAgent(search_tool, tracer, logger)
    sql_safety = SQLSafetyGuardAgent(sql_policy, limits_policy, tracer, logger)
    db_executor = DBExecutorAgent(db_tool, limits_policy, tracer, logger)

    agent_manager = AgentManager(logger=logger)
    max_retries = int(os.environ.get("MAX_RETRY_ATTEMPTS", "5"))

    fallback = FallbackOrchestrator(
        agent_manager=agent_manager,
        metadata_retriever=metadata_retriever,
        sql_safety=sql_safety,
        db_executor=db_executor,
        llm_tool=llm_tool,
        tracer=tracer,
        logger=logger,
        max_retry_attempts=max_retries,
    )

    return Orchestrator(
        agent_manager=agent_manager,
        tracer=tracer,
        logger=logger,
        fallback=fallback,
    )


def handle_chat(req):
    orch = build_orchestrator()
    return orch.run(req)
