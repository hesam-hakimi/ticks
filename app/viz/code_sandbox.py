"""app.viz.code_sandbox

Executes LLM-generated visualization code in a restricted sandbox.

Security goals:
- No imports inside generated code
- Restricted builtins
- Pre-provided safe libraries only
- Timeout enforcement (separate process)

Contract:
- Code must assign final chart object to variable `fig`.
- `fig` can be:
    - Plotly Figure (preferred)
    - Matplotlib Figure (seaborn/matplotlib)
"""

from __future__ import annotations

import ast
import multiprocessing as mp
from dataclasses import dataclass
from typing import Any, Optional

import pandas as pd


@dataclass
class SandboxResult:
    ok: bool
    error: Optional[str]
    fig: Any | None


_BLOCKED_NAMES = {
    "__import__", "eval", "exec", "compile", "open", "input",
    "os", "sys", "subprocess", "socket", "pathlib", "shutil",
    "requests", "urllib", "http", "ftplib",
}


def _validate_ast(code: str) -> None:
    tree = ast.parse(code, mode="exec")
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            raise ValueError("Imports are not allowed in visualization code.")
        if isinstance(node, ast.Call):
            # Block direct calls to dangerous builtins if referenced by name
            if isinstance(node.func, ast.Name) and node.func.id in _BLOCKED_NAMES:
                raise ValueError(f"Call to blocked function: {node.func.id}")
        if isinstance(node, ast.Name) and node.id in _BLOCKED_NAMES:
            raise ValueError(f"Use of blocked name: {node.id}")


def _worker(code: str, df: pd.DataFrame, q: mp.Queue) -> None:
    try:
        _validate_ast(code)

        # Pre-import allowed libs in worker
        import plotly.express as px  # allowed outside generated code
        import plotly.graph_objects as go
        import seaborn as sns
        import matplotlib.pyplot as plt

        safe_builtins = {
            "len": len, "range": range, "min": min, "max": max, "sum": sum,
            "abs": abs, "sorted": sorted, "round": round, "str": str, "int": int, "float": float,
            "list": list, "dict": dict, "set": set, "tuple": tuple,
        }

        g = {"__builtins__": safe_builtins, "df": df, "px": px, "go": go, "sns": sns, "plt": plt}
        l: dict[str, Any] = {}

        exec(code, g, l)  # code is AST-validated + restricted builtins

        fig = l.get("fig") or g.get("fig")
        if fig is None:
            # seaborn often draws on current figure
            fig = plt.gcf()

        q.put({"ok": True, "error": None, "fig": fig})
    except Exception as e:
        q.put({"ok": False, "error": str(e), "fig": None})


def run_viz_code(code: str, df: pd.DataFrame, timeout_seconds: int = 5) -> SandboxResult:
    """Execute code in a separate process with a strict timeout."""
    q: mp.Queue = mp.Queue()
    p = mp.Process(target=_worker, args=(code, df, q))
    p.start()
    p.join(timeout_seconds)

    if p.is_alive():
        p.terminate()
        p.join(1)
        return SandboxResult(ok=False, error=f"Visualization code timed out after {timeout_seconds}s", fig=None)

    if q.empty():
        return SandboxResult(ok=False, error="No result returned from sandbox", fig=None)

    out = q.get()
    return SandboxResult(ok=bool(out.get("ok")), error=out.get("error"), fig=out.get("fig"))
