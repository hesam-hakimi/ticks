"""app.config

Centralized configuration for the application.

Uses environment variables to avoid hardcoded secrets.
"""

from __future__ import annotations
from dataclasses import dataclass
import os


def _env(name: str, default: str | None = None) -> str | None:
    val = os.getenv(name)
    return val if val is not None else default


def _env_bool(name: str, default: bool = False) -> bool:
    v = os.getenv(name)
    if v is None:
        return default
    return v.strip().lower() in ("1", "true", "yes", "y", "on")


def _env_int(name: str, default: int) -> int:
    v = os.getenv(name)
    if v is None:
        return default
    try:
        return int(v)
    except ValueError:
        return default


@dataclass(frozen=True)
class Settings:
    """Application settings loaded from environment variables."""

    # Managed Identity
    msi_client_id: str | None

    # Azure AI Search
    azure_search_endpoint: str
    index_field: str
    index_table: str
    index_relationship: str
    index_common_queries: str

    # Azure OpenAI
    azure_openai_endpoint: str
    azure_openai_chat_deployment: str

    # DB
    db_backend: str  # sqlserver|sqlite
    azure_sql_server: str | None
    azure_sql_database: str | None
    azure_sql_conn_str: str | None
    sqlite_path: str

    # UI defaults
    default_max_rows: int
    default_max_cols: int
    default_timeout_seconds: int
    default_debug: bool

    # Logging
    log_dir: str

    @staticmethod
    def load() -> "Settings":
        return Settings(
            msi_client_id=_env("AZURE_MSI_CLIENT_ID"),
            azure_search_endpoint=_env("AZURE_SEARCH_ENDPOINT", "") or "",
            index_field=_env("AZURE_SEARCH_INDEX_FIELD", "meta_data_field") or "meta_data_field",
            index_table=_env("AZURE_SEARCH_INDEX_TABLE", "meta_data_table") or "meta_data_table",
            index_relationship=_env("AZURE_SEARCH_INDEX_RELATIONSHIP", "meta_data_relationship") or "meta_data_relationship",
            index_common_queries=_env("AZURE_SEARCH_INDEX_COMMON_QUERIES", "common_queries") or "common_queries",
            azure_openai_endpoint=_env("AZURE_OPENAI_ENDPOINT", "") or "",
            azure_openai_chat_deployment=_env("AZURE_OPENAI_CHAT_DEPLOYMENT", "") or "",
            db_backend=(_env("DB_BACKEND", "sqlserver") or "sqlserver").strip().lower(),
            azure_sql_server=_env("AZURE_SQL_SERVER"),
            azure_sql_database=_env("AZURE_SQL_DATABASE"),
            azure_sql_conn_str=_env("AZURE_SQL_CONN_STR"),
            sqlite_path=_env("SQLITE_PATH", "data/app.db") or "data/app.db",
            default_max_rows=_env_int("UI_DEFAULT_MAX_ROWS", 50),
            default_max_cols=_env_int("UI_DEFAULT_MAX_COLS", 20),
            default_timeout_seconds=_env_int("UI_DEFAULT_TIMEOUT_SECONDS", 20),
            default_debug=_env_bool("UI_DEFAULT_DEBUG", False),
            log_dir=_env("LOG_DIR", "logs") or "logs",
        )
