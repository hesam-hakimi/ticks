"""app.policy.sql_policy

Read-only SQL validation.

This is intentionally conservative. For production, extend with:
- allowlist of schemas/tables/views
- deeper parsing (if company_name allows a SQL parser library)
"""

from __future__ import annotations
import re
from typing import List


_DENY_KEYWORDS = [
    "insert", "update", "delete", "merge",
    "drop", "alter", "create", "truncate",
    "grant", "revoke", "execute", "exec",
    "xp_", "sp_", "openrowset", "opendatasource",
]

_DENY_PATTERN = re.compile(r"\b(" + "|".join(re.escape(k) for k in _DENY_KEYWORDS) + r")\b", re.IGNORECASE)


class SqlPolicy:
    """Validates and enforces read-only SQL policy."""

    def validate(self, sql: str) -> List[str]:
        """Return a list of violations; empty means 'looks safe'."""
        s = (sql or "").strip()
        violations: List[str] = []

        if not s:
            return ["Empty SQL"]

        # Block multiple statements (allow a trailing semicolon only)
        if ";" in s[:-1]:
            violations.append("Multiple statements are not allowed")

        # Block comments (strict mode)
        if "--" in s or "/*" in s or "*/" in s:
            violations.append("SQL comments are not allowed")

        # Must start with SELECT or WITH (CTE)
        low = s.lower()
        if not (low.startswith("select") or low.startswith("with")):
            violations.append("Only SELECT queries are allowed")

        if _DENY_PATTERN.search(s):
            violations.append("DDL/DML or unsafe keyword detected")

        return violations
