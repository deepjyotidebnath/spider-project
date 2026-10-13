"""Schema data model + loaders (Spider tables.json and SQLite introspection)."""
from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Column:
    name: str
    type: str = "text"
    is_pk: bool = False


@dataclass
class Table:
    name: str
    columns: list[Column] = field(default_factory=list)


@dataclass
class ForeignKey:
    table: str
    column: str
    ref_table: str
    ref_column: str


@dataclass
class Schema:
    db_id: str
    tables: list[Table]
    foreign_keys: list[ForeignKey] = field(default_factory=list)

    @property
    def n_tables(self) -> int:
        return len(self.tables)

    @property
    def n_columns(self) -> int:
        return sum(len(t.columns) for t in self.tables)


def load_tables_json(path: str | Path) -> dict[str, Schema]:
    """Parse Spider's ``tables.json`` into ``{db_id: Schema}``."""
    with open(path, encoding="utf-8") as f:
        raw = json.load(f)

    schemas: dict[str, Schema] = {}
    for db in raw:
        tnames = db["table_names_original"]
        cols = db["column_names_original"]  # [[table_idx, col_name], ...]
        ctypes = db["column_types"]

        pk_idx: set[int] = set()
        for pk in db.get("primary_keys", []):
            if isinstance(pk, list):
                pk_idx.update(pk)
            else:
                pk_idx.add(pk)

        tables = [Table(name=n) for n in tnames]
        for i, (t_idx, cname) in enumerate(cols):
            if t_idx < 0:  # the "*" pseudo-column
                continue
            tables[t_idx].columns.append(Column(cname, ctypes[i], i in pk_idx))

        fks = []
        for a, b in db.get("foreign_keys", []):
            ta, ca = cols[a]
            tb, cb = cols[b]
            fks.append(ForeignKey(tnames[ta], ca, tnames[tb], cb))

        schemas[db["db_id"]] = Schema(db["db_id"], tables, fks)
    return schemas


def schema_from_sqlite(db_path: str | Path, db_id: str | None = None) -> Schema:
    """Build a Schema by introspecting a SQLite file."""
    db_path = Path(db_path)
    db_id = db_id or db_path.stem
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    conn.text_factory = lambda b: b.decode("utf-8", errors="replace")
    try:
        names = [
            r[0]
            for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' "
                "AND name NOT LIKE 'sqlite_%' ORDER BY rowid"
            )
        ]
        tables, fks = [], []
        for t in names:
            info = conn.execute(f'PRAGMA table_info("{t}")').fetchall()
            tables.append(
                Table(t, [Column(r[1], (r[2] or "text").lower(), bool(r[5])) for r in info])
            )
            for r in conn.execute(f'PRAGMA foreign_key_list("{t}")'):
                # (id, seq, table, from, to, ...)
                if r[4] is not None:
                    fks.append(ForeignKey(t, r[3], r[2], r[4]))
        return Schema(db_id, tables, fks)
    finally:
        conn.close()


def find_sqlite(db_dir: str | Path, db_id: str) -> Path | None:
    """Spider layout: ``<db_dir>/<db_id>/<db_id>.sqlite``."""
    p = Path(db_dir) / db_id / f"{db_id}.sqlite"
    return p if p.exists() else None


def sample_rows(db_path: str | Path, table: str, n: int = 3) -> tuple[list[str], list[tuple]]:
    """Return (column_names, first n rows) of a table."""
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    conn.text_factory = lambda b: b.decode("utf-8", errors="replace")
    try:
        cur = conn.execute(f'SELECT * FROM "{table}" LIMIT {int(n)}')
        return [d[0] for d in cur.description], cur.fetchall()
    finally:
        conn.close()
