"""app.env_loader

Loads environment variables from a .env file using python-dotenv.

Why:
- Keeps local/dev/VM runs simple: you can store AZURE_* settings in a .env file.
- Works with Streamlit (which can run from different working directories).
- Does NOT override already-set environment variables by default.

Usage:
    from app.env_loader import load_env
    load_env()  # finds nearest .env
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from dotenv import load_dotenv


def _find_dotenv(start: Path, max_levels: int = 6) -> Optional[Path]:
    """Search upward for a .env file starting from `start`."""
    cur = start.resolve()
    for _ in range(max_levels + 1):
        candidate = cur / ".env"
        if candidate.exists():
            return candidate
        if cur.parent == cur:
            break
        cur = cur.parent
    return None


def load_env(dotenv_path: str | None = None, override: bool = False) -> str | None:
    """Load env vars from .env.

    Args:
        dotenv_path: Optional explicit path to .env. If not provided, we search upward from CWD.
        override: If True, values in .env override existing env vars. Default False (safer).

    Returns:
        The .env path used, or None if no .env was found.
    """
    path: Optional[Path]
    if dotenv_path:
        path = Path(dotenv_path).expanduser()
        if not path.exists():
            return None
    else:
        path = _find_dotenv(Path.cwd())

    if not path:
        return None

    load_dotenv(dotenv_path=str(path), override=override)
    return str(path)
