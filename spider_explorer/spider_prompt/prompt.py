"""Schema serialization and prompt construction."""
from __future__ import annotations

from pathlib import Path

from .schema import Schema, find_sqlite, sample_rows

STYLES = {
    "create_table": "CREATE TABLE statements (with PK/FK constraints)",
    "compact": "Compact: table(col, col, ...) plus foreign-key lines",
    "markdown": "Markdown list of tables with typed columns",
}

DEFAULT_INSTRUCTION = (
    "Given the database schema below, write a SQLite query that answers the question. "
    "Return only the SQL."
)


def _q(name: str) -> str:
    """Quote an identifier only when needed."""
    return name if name.replace("_", "").isalnum() and not name[0].isdigit() else f'"{name}"'


def _serialize_create_table(schema: Schema) -> str:
    blocks = []
    for t in schema.tables:
        lines = [f"  {_q(c.name)} {c.type.upper()}" for c in t.columns]
        pks = [_q(c.name) for c in t.columns if c.is_pk]
        if pks:
            lines.append(f"  PRIMARY KEY ({', '.join(pks)})")
        for fk in schema.foreign_keys:
            if fk.table == t.name:
                lines.append(
                    f"  FOREIGN KEY ({_q(fk.column)}) REFERENCES {_q(fk.ref_table)}({_q(fk.ref_column)})"
                )
        blocks.append(f"CREATE TABLE {_q(t.name)} (\n" + ",\n".join(lines) + "\n);")
    return "\n\n".join(blocks)


def _serialize_compact(schema: Schema) -> str:
    lines = [f"{t.name}({', '.join(c.name for c in t.columns)})" for t in schema.tables]
    if schema.foreign_keys:
        lines.append("Foreign keys:")
        lines += [
            f"{fk.table}.{fk.column} = {fk.ref_table}.{fk.ref_column}" for fk in schema.foreign_keys
        ]
    return "\n".join(lines)


def _serialize_markdown(schema: Schema) -> str:
    out = []
    for t in schema.tables:
        out.append(f"### {t.name}")
        for c in t.columns:
            tag = " (primary key)" if c.is_pk else ""
            out.append(f"- {c.name}: {c.type}{tag}")
        out.append("")
    if schema.foreign_keys:
        out.append("### Foreign keys")
        out += [
            f"- {fk.table}.{fk.column} -> {fk.ref_table}.{fk.ref_column}"
            for fk in schema.foreign_keys
        ]
    return "\n".join(out).rstrip()


def serialize_schema(
    schema: Schema,
    style: str = "create_table",
    db_dir: str | Path | None = None,
    n_rows: int = 0,
) -> str:
    """Turn a Schema into text. Optionally append sample rows from SQLite files."""
    if style == "create_table":
        text = _serialize_create_table(schema)
    elif style == "compact":
        text = _serialize_compact(schema)
    elif style == "markdown":
        text = _serialize_markdown(schema)
    else:
        raise ValueError(f"Unknown style {style!r}; choose from {list(STYLES)}")

    if n_rows > 0 and db_dir:
        path = find_sqlite(db_dir, schema.db_id)
        if path:
            extra = []
            for t in schema.tables:
                try:
                    cols, rows = sample_rows(path, t.name, n_rows)
                except Exception:
                    continue
                extra.append(f"/* {t.name}: {n_rows} example rows */")
                extra.append(" | ".join(cols))
                extra += [" | ".join(str(v) for v in r) for r in rows]
                extra.append("")
            if extra:
                text += "\n\n" + "\n".join(extra).rstrip()
    return text


def build_prompt(
    question: str,
    schema: Schema | str,
    style: str = "create_table",
    instruction: str | None = DEFAULT_INSTRUCTION,
    db_dir: str | Path | None = None,
    n_rows: int = 0,
    answer_prefix: str = "SQL:",
) -> str:
    """Build a clean text prompt from a question and a database schema.

    ``schema`` may be a :class:`Schema` or an already serialized string.
    """
    schema_text = (
        schema if isinstance(schema, str) else serialize_schema(schema, style, db_dir, n_rows)
    )
    parts = []
    if instruction:
        parts.append(instruction.strip())
    parts.append("### Database schema\n" + schema_text.strip())
    parts.append("### Question\n" + question.strip())
    parts.append("### Answer\n" + answer_prefix)
    return "\n\n".join(parts)


def build_messages(question: str, schema: Schema | str, **kwargs) -> list[dict]:
    """Same content as :func:`build_prompt`, split into chat messages."""
    instruction = kwargs.pop("instruction", DEFAULT_INSTRUCTION)
    user = build_prompt(question, schema, instruction=None, **kwargs)
    return [
        {"role": "system", "content": instruction},
        {"role": "user", "content": user},
    ]
