from spider_prompt import (
    SchemaStore, build_messages, build_prompt, classify_difficulty, load_sample,
    serialize_schema,
)


def test_difficulty_levels():
    assert classify_difficulty("SELECT count(*) FROM singer") == "easy"
    assert classify_difficulty("SELECT name FROM singer WHERE age > 20") == "easy"
    assert classify_difficulty(
        "SELECT name, country, age FROM singer ORDER BY age DESC") in {"medium", "easy"}
    assert classify_difficulty(
        "SELECT avg(age), min(age), max(age) FROM singer WHERE country = 'France'") == "medium"
    assert classify_difficulty(
        "SELECT name FROM stadium WHERE stadium_id NOT IN (SELECT stadium_id FROM concert)") == "hard"
    assert classify_difficulty(
        "SELECT country FROM singer WHERE age > 40 INTERSECT SELECT country FROM singer WHERE age < 30"
    ) in {"hard", "extra"}


def test_sample_dataframe():
    df = load_sample()
    assert {"split", "db_id", "question", "query", "difficulty"} <= set(df.columns)
    assert df.difficulty.isin(["easy", "medium", "hard", "extra"]).all()


def test_schema_styles_and_prompt():
    store = SchemaStore()
    s = store.get("concert_singer")
    assert "CREATE TABLE singer" in serialize_schema(s, "create_table")
    assert "singer(" in serialize_schema(s, "compact")
    assert "### singer" in serialize_schema(s, "markdown")
    p = build_prompt("How many singers?", s)
    assert "How many singers?" in p and "CREATE TABLE" in p and p.rstrip().endswith("SQL:")
    msgs = build_messages("How many singers?", s)
    assert [m["role"] for m in msgs] == ["system", "user"]


def test_string_schema_passthrough():
    assert "my schema" in build_prompt("q", "my schema")
