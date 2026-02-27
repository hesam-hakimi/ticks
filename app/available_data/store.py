"""app.available_data.store

Loads "currently available" datasets from local files into memory.

- Designed for small summarized datasets (<~5000 rows each).
- Primary goal: fast response without DB latency.
- Supports JSON Lines (.jsonl) and JSON array (.json) files.

Environment variables:
  AVAILABLE_DATA_DIR: path to folder containing dataset files (default: <repo>/data/available_json)
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional

import pandas as pd

from app.paths import data_dir


@dataclass
class DatasetInfo:
    name: str
    path: Path
    format: str  # jsonl|json

    def load(self) -> pd.DataFrame:
        if self.format == "jsonl":
            return pd.read_json(self.path, lines=True)
        if self.format == "json":
            return pd.read_json(self.path)
        raise ValueError(f"Unsupported dataset format: {self.format}")


class AvailableDataStore:
    """In-memory store for available datasets."""

    def __init__(self, base_dir: Optional[str] = None):
        if base_dir:
            self.base_dir = Path(base_dir).expanduser()
        else:
            self.base_dir = Path(
                __import__("os").environ.get("AVAILABLE_DATA_DIR", str(data_dir() / "available_json"))
            )
        self.base_dir = self.base_dir.resolve()
        self._catalog: Dict[str, DatasetInfo] = {}
        self._cache: Dict[str, pd.DataFrame] = {}
        self._build_catalog()

    def _build_catalog(self) -> None:
        self._catalog.clear()
        if not self.base_dir.exists():
            return
        for p in self.base_dir.glob("*.jsonl"):
            self._catalog[p.stem] = DatasetInfo(name=p.stem, path=p, format="jsonl")
        for p in self.base_dir.glob("*.json"):
            # Only register .json if .jsonl is not present
            if p.stem not in self._catalog:
                self._catalog[p.stem] = DatasetInfo(name=p.stem, path=p, format="json")

    def list_datasets(self) -> list[str]:
        return sorted(self._catalog.keys())

    def has_dataset(self, name: str) -> bool:
        return name in self._catalog

    def get_df(self, name: str, refresh: bool = False) -> pd.DataFrame:
        if not refresh and name in self._cache:
            return self._cache[name]
        info = self._catalog.get(name)
        if not info:
            raise KeyError(f"Dataset not found: {name}")
        df = info.load()
        self._cache[name] = df
        return df

    def schema(self, name: str) -> list[str]:
        df = self.get_df(name)
        return list(df.columns)
