# Spider Dataset Explorer & Prompt Builder

A Streamlit app + notebook that loads the [Spider](https://yale-lily.github.io/spider) text-to-SQL
dataset, shows dataset statistics and query difficulty levels, and turns every
(question, database schema) pair into a clean text prompt via `build_prompt(question, schema)`.

## Quick start

```bash
pip install -r requirements.txt
streamlit run app.py          # runs offline with the built-in sample
jupyter notebook spider_explorer.ipynb
pytest -q
```

## Using the real dataset

1. In the app sidebar choose **Hugging Face (xlangai/spider)** (needs internet on first load).
2. The Hugging Face copy contains only `db_id`, `question`, `query` and **no schemas**.
   Download the original Spider release (it ships `tables.json` and a `database/` folder of
   SQLite files), then set the sidebar paths:
   - `tables.json path` → schemas for every database
   - `SQLite database folder` → fallback schema introspection and sample rows in prompts
3. Or choose **Local Spider folder** to read `train_spider.json`, `train_others.json`, `dev.json`
   from the unzipped release; paths for `tables.json` and `database/` are filled in automatically.

## Project layout

```
app.py                  Streamlit UI (statistics, browse, prompt builder, JSONL export)
spider_explorer.ipynb   Notebook version of the same workflow
spider_prompt/
  schema.py             Schema model; tables.json + SQLite loaders
  difficulty.py         easy/medium/hard/extra classifier
  prompt.py             serialize_schema(), build_prompt(), build_messages()
  data.py               HF / local / sample loaders, SchemaStore
  sample_data.py        Tiny offline sample (2 databases, 13 examples)
tests/test_core.py
```

## Notes

- **Difficulty:** Spider's official hardness needs parsed SQL, which the HF copy lacks.
  `difficulty.py` re-implements the same counting rules (component1/component2/others) on the
  raw SQL string, so levels are a close approximation, not an exact match to the official labels.
- **Prompt formats:** `create_table` (default), `compact`, `markdown`; optional sample rows per table.

```python
from spider_prompt import SchemaStore, build_prompt
store = SchemaStore("spider/tables.json", "spider/database")
print(build_prompt("How many singers do we have?", store.get("concert_singer")))
```
