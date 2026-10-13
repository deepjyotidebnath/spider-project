"""Dataset loading: Hugging Face, local Spider files, or the built-in sample."""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from .difficulty import classify_difficulty, sql_features
from .sample_data import SAMPLE_EXAMPLES, SAMPLE_SCHEMAS
from .schema import Schema, find_sqlite, load_tables_json, schema_from_sqlite

HF_NAME = "xlangai/spider"


def _finalize(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["difficulty"] = df["query"].map(classify_difficulty)
    feats = pd.DataFrame([sql_features(q) for q in df["query"]])
    df["n_join"] = feats["n_join"].values
    df["n_agg"] = feats["n_agg"].values
    df["has_nested"] = (feats["n_nested"] + feats["n_set_ops"]).values > 0
    df["has_group"] = feats["has_group"].values
    df["has_order"] = feats["has_order"].values
    df["question_words"] = df["question"].str.split().str.len()
    df["query_chars"] = df["query"].str.len()
    return df.reset_index(drop=True)


def load_sample() -> pd.DataFrame:
    rows = [
        {"split": s, "db_id": d, "question": q, "query": sql} for d, q, sql, s in SAMPLE_EXAMPLES
    ]
    return _finalize(pd.DataFrame(rows))


def load_hf() -> pd.DataFrame:
    """Load Spider (train + validation) from the Hugging Face Hub."""
    from datasets import load_dataset  # imported lazily

    ds = load_dataset(HF_NAME)
    frames = []
    for split, d in ds.items():
        part = d.to_pandas()[["db_id", "question", "query"]]
        part.insert(0, "split", split)
        frames.append(part)
    return _finalize(pd.concat(frames, ignore_index=True))


def load_local(spider_dir: str | Path) -> pd.DataFrame:
    """Load from an unzipped original Spider folder (train_spider.json, dev.json, ...)."""
    spider_dir = Path(spider_dir)
    files = {
        "train": "train_spider.json",
        "train_others": "train_others.json",
        "validation": "dev.json",
    }
    frames = []
    for split, fname in files.items():
        p = spider_dir / fname
        if p.exists():
            with open(p, encoding="utf-8") as f:
                data = json.load(f)
            frames.append(
                pd.DataFrame(
                    {
                        "split": split,
                        "db_id": [x["db_id"] for x in data],
                        "question": [x["question"] for x in data],
                        "query": [x["query"] for x in data],
                    }
                )
            )
    if not frames:
        raise FileNotFoundError(f"No train_spider.json / dev.json found in {spider_dir}")
    return _finalize(pd.concat(frames, ignore_index=True))


class SchemaStore:
    """Looks up a Schema by db_id from tables.json, SQLite files, or the sample."""

    def __init__(self, tables_json: str | Path | None = None, db_dir: str | Path | None = None):
        self.db_dir = Path(db_dir) if db_dir else None
        self._schemas: dict[str, Schema] = dict(SAMPLE_SCHEMAS)
        if tables_json and Path(tables_json).exists():
            self._schemas.update(load_tables_json(tables_json))

    def get(self, db_id: str) -> Schema | None:
        if db_id in self._schemas:
            return self._schemas[db_id]
        if self.db_dir:
            path = find_sqlite(self.db_dir, db_id)
            if path:
                self._schemas[db_id] = schema_from_sqlite(path, db_id)
                return self._schemas[db_id]
        return None

    def __len__(self) -> int:
        return len(self._schemas)
