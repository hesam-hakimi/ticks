"""app.paths

Helpers for resolving file system paths consistently (Streamlit can run from different CWDs).
"""

from __future__ import annotations
from pathlib import Path


def project_root() -> Path:
    """Return the repository root folder (parent of `app/`)."""
    return Path(__file__).resolve().parents[1]


def data_dir() -> Path:
    """Return the default data directory under the repo."""
    return project_root() / "data"
