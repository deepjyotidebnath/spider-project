"""Spider Dataset Explorer & Prompt Builder (Streamlit)."""
from __future__ import annotations

import json

import pandas as pd
import streamlit as st

from spider_prompt import (
    LEVELS,
    STYLES,
    SchemaStore,
    build_messages,
    build_prompt,
    load_hf,
    load_local,
    load_sample,
    serialize_schema,
)
from spider_prompt.prompt import DEFAULT_INSTRUCTION

st.set_page_config(page_title="Spider Explorer", page_icon="🕷️", layout="wide")


# ---------------------------------------------------------------- data loading
@st.cache_data(show_spinner="Loading dataset…")
def get_data(source: str, spider_dir: str) -> pd.DataFrame:
    if source == "Hugging Face (xlangai/spider)":
        return load_hf()
    if source == "Local Spider folder":
        return load_local(spider_dir)
    return load_sample()


@st.cache_resource
def get_store(tables_json: str, db_dir: str) -> SchemaStore:
    return SchemaStore(tables_json or None, db_dir or None)


with st.sidebar:
    st.title("🕷️ Spider Explorer")
    source = st.radio(
        "Dataset source",
        ["Built-in sample (offline)", "Hugging Face (xlangai/spider)", "Local Spider folder"],
    )
    spider_dir = ""
    if source == "Local Spider folder":
        spider_dir = st.text_input("Spider folder", placeholder="/path/to/spider")

    st.subheader("Schemas")
    st.caption(
        "The Hugging Face copy has no schemas. Point to Spider's `tables.json` "
        "and/or its `database/` folder to get them."
    )
    default_tables = f"{spider_dir}/tables.json" if spider_dir else ""
    tables_json = st.text_input("tables.json path", value=default_tables)
    default_db = f"{spider_dir}/database" if spider_dir else ""
    db_dir = st.text_input("SQLite database folder", value=default_db)

try:
    df = get_data(source, spider_dir)
except Exception as e:  # noqa: BLE001
    st.error(f"Could not load dataset: {e}")
    st.stop()

store = get_store(tables_json, db_dir)

st.title("Spider Dataset Explorer & Prompt Builder")
st.caption(
    f"{len(df):,} examples · {df['db_id'].nunique()} databases · "
    "difficulty is a heuristic re-implementation of Spider's hardness rules."
)

tab_stats, tab_browse, tab_prompt = st.tabs(["📊 Statistics", "🔎 Browse", "🧩 Prompt builder"])

# ------------------------------------------------------------------ statistics
with tab_stats:
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Examples", f"{len(df):,}")
    c2.metric("Databases", df["db_id"].nunique())
    c3.metric("Avg question words", f"{df['question_words'].mean():.1f}")
    c4.metric("Avg SQL chars", f"{df['query_chars'].mean():.0f}")

    left, right = st.columns(2)
    with left:
        st.subheader("Difficulty levels")
        diff = df["difficulty"].value_counts().reindex(LEVELS, fill_value=0)
        st.bar_chart(diff)
        st.dataframe(
            (diff / diff.sum() * 100).round(1).rename("percent").to_frame(), width="stretch"
        )
    with right:
        st.subheader("Examples per split")
        st.bar_chart(df["split"].value_counts())
        st.subheader("Difficulty by split")
        st.dataframe(pd.crosstab(df["split"], df["difficulty"]).reindex(columns=LEVELS, fill_value=0))

    st.subheader("SQL feature prevalence")
    feats = pd.Series(
        {
            "JOIN": (df["n_join"] > 0).mean(),
            "Aggregation": (df["n_agg"] > 0).mean(),
            "GROUP BY": df["has_group"].mean(),
            "ORDER BY": df["has_order"].mean(),
            "Nested / set-op": df["has_nested"].mean(),
        }
    )
    st.bar_chart((feats * 100).round(1))

    st.subheader("Top databases")
    st.bar_chart(df["db_id"].value_counts().head(20))

    st.subheader("Schema size")
    rows = []
    for db in sorted(df["db_id"].unique()):
        s = store.get(db)
        if s:
            rows.append({"db_id": db, "tables": s.n_tables, "columns": s.n_columns,
                         "foreign_keys": len(s.foreign_keys)})
    if rows:
        st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)
    else:
        st.info("No schemas available for these databases yet — set `tables.json` in the sidebar.")

# ---------------------------------------------------------------------- browse
with tab_browse:
    f1, f2, f3 = st.columns(3)
    splits = f1.multiselect("Split", sorted(df["split"].unique()), default=sorted(df["split"].unique()))
    diffs = f2.multiselect("Difficulty", LEVELS, default=LEVELS)
    dbs = f3.multiselect("Database", sorted(df["db_id"].unique()))
    text = st.text_input("Search question or SQL")

    view = df[df["split"].isin(splits) & df["difficulty"].isin(diffs)]
    if dbs:
        view = view[view["db_id"].isin(dbs)]
    if text:
        mask = view["question"].str.contains(text, case=False, regex=False) | view[
            "query"
        ].str.contains(text, case=False, regex=False)
        view = view[mask]

    st.caption(f"{len(view):,} matching examples")
    st.dataframe(
        view[["split", "db_id", "difficulty", "question", "query"]],
        width="stretch",
        hide_index=True,
        height=420,
    )

# -------------------------------------------------------------- prompt builder
with tab_prompt:
    st.subheader("Build a prompt")
    opt1, opt2, opt3 = st.columns(3)
    style = opt1.selectbox("Schema format", list(STYLES), format_func=lambda k: STYLES[k])
    n_rows = opt2.number_input("Sample rows per table (needs SQLite folder)", 0, 10, 0)
    answer_prefix = opt3.text_input("Answer prefix", value="SQL:")
    instruction = st.text_area("Instruction", value=DEFAULT_INSTRUCTION, height=80)

    pool = df.reset_index(drop=True)
    idx = st.number_input("Example index", 0, len(pool) - 1, 0)
    ex = pool.iloc[int(idx)]
    schema = store.get(ex["db_id"])

    st.markdown(f"**{ex['db_id']}** · `{ex['split']}` · difficulty: **{ex['difficulty']}**")
    st.markdown(f"**Question:** {ex['question']}")
    st.markdown("**Gold SQL:**")
    st.code(ex["query"], language="sql")

    if schema is None:
        st.warning(
            f"No schema found for `{ex['db_id']}`. Set `tables.json` or the SQLite folder in the sidebar."
        )
    else:
        prompt = build_prompt(
            ex["question"], schema, style=style, instruction=instruction or None,
            db_dir=db_dir or None, n_rows=int(n_rows), answer_prefix=answer_prefix,
        )
        st.markdown("**Prompt**")
        st.code(prompt, language="markdown")
        a, b = st.columns(2)
        a.download_button("Download prompt (.txt)", prompt, file_name=f"prompt_{int(idx)}.txt")
        msgs = build_messages(
            ex["question"], schema, style=style, instruction=instruction or DEFAULT_INSTRUCTION,
            db_dir=db_dir or None, n_rows=int(n_rows), answer_prefix=answer_prefix,
        )
        b.download_button(
            "Download chat messages (.json)", json.dumps(msgs, indent=2), file_name=f"messages_{int(idx)}.json"
        )

    st.divider()
    st.subheader("Batch export (JSONL)")
    st.caption("Exports the examples currently selected in the Browse tab.")
    limit = st.number_input("Max examples", 1, max(1, len(view)), min(100, max(1, len(view))))
    if st.button("Generate JSONL"):
        lines, skipped = [], 0
        for _, r in view.head(int(limit)).iterrows():
            s = store.get(r["db_id"])
            if s is None:
                skipped += 1
                continue
            lines.append(
                json.dumps(
                    {
                        "db_id": r["db_id"],
                        "difficulty": r["difficulty"],
                        "prompt": build_prompt(
                            r["question"], s, style=style, instruction=instruction or None,
                            db_dir=db_dir or None, n_rows=int(n_rows), answer_prefix=answer_prefix,
                        ),
                        "gold_sql": r["query"],
                    }
                )
            )
        st.success(f"{len(lines)} prompts generated" + (f", {skipped} skipped (no schema)" if skipped else ""))
        if lines:
            st.download_button("Download prompts.jsonl", "\n".join(lines), file_name="prompts.jsonl")
