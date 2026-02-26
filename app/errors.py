"""app.errors

Central error types to keep error handling consistent.
"""


class AppError(Exception):
    """Base application error."""


class ConfigError(AppError):
    """Raised when required configuration is missing or invalid."""


class UnsafeSQLError(AppError):
    """Raised when SQL violates read-only/safety policy."""


class ToolError(AppError):
    """Raised when an external tool call fails (Search, LLM, DB)."""


class LLMOutputError(AppError):
    """Raised when the LLM output cannot be parsed/validated."""
