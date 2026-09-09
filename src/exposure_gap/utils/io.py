"""Small IO helpers shared across phases."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable

import pandas as pd


def ensure_dir(path: str | Path) -> Path:
    p = Path(path)
    p.mkdir(parents=True, exist_ok=True)
    return p


def write_json(obj: Any, path: str | Path, *, sort_keys: bool = True) -> Path:
    p = Path(path)
    ensure_dir(p.parent)
    p.write_text(json.dumps(obj, indent=2, sort_keys=sort_keys, default=str))
    return p


def read_json(path: str | Path) -> Any:
    return json.loads(Path(path).read_text())


def write_jsonl(rows: Iterable[dict], path: str | Path) -> Path:
    p = Path(path)
    ensure_dir(p.parent)
    with p.open("w") as fh:
        for row in rows:
            fh.write(json.dumps(row, default=str) + "\n")
    return p


def read_jsonl(path: str | Path) -> list[dict]:
    with Path(path).open() as fh:
        return [json.loads(ln) for ln in fh if ln.strip()]


def write_table(df: pd.DataFrame, path: str | Path) -> Path:
    p = Path(path)
    ensure_dir(p.parent)
    if p.suffix == ".parquet":
        df.to_parquet(p, index=False)
    else:
        df.to_csv(p, index=False)
    return p


def read_table(path: str | Path) -> pd.DataFrame:
    p = Path(path)
    return pd.read_parquet(p) if p.suffix == ".parquet" else pd.read_csv(p)
