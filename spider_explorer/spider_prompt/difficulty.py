"""Heuristic Spider-style difficulty classifier.

The Hugging Face copy of Spider has no parsed SQL, so the official
``evaluation.py`` hardness rules cannot be applied directly. This module
re-implements the same counting rules (component1 / component2 / others)
on the raw SQL string. It is an approximation, not an exact reproduction.
"""
from __future__ import annotations

import re

LEVELS = ["easy", "medium", "hard", "extra"]

_STR = re.compile(r"'[^']*'|\"[^\"]*\"")
_AGG = re.compile(r"\b(?:count|sum|avg|min|max)\s*\(")
_SET_OPS = re.compile(r"\b(?:intersect|union|except)\b")


def _norm(sql: str) -> str:
    s = _STR.sub("'v'", sql.lower())
    return re.sub(r"\s+", " ", s).strip().rstrip(";")


def _strip_subqueries(s: str) -> tuple[str, int]:
    """Remove balanced ``(select ...)`` blocks; return (text, number removed)."""
    count = 0
    while True:
        m = re.search(r"\(\s*select\b", s)
        if not m:
            return s, count
        depth, i = 0, m.start()
        while i < len(s):
            if s[i] == "(":
                depth += 1
            elif s[i] == ")":
                depth -= 1
                if depth == 0:
                    break
            i += 1
        s = s[: m.start()] + " _sub_ " + s[i + 1 :]
        count += 1


def _split_top_level_commas(s: str) -> list[str]:
    parts, depth, cur = [], 0, []
    for ch in s:
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        if ch == "," and depth == 0:
            parts.append("".join(cur))
            cur = []
        else:
            cur.append(ch)
    parts.append("".join(cur))
    return [p.strip() for p in parts if p.strip()]


def _clause(text: str, start: str, ends: list[str]) -> str:
    m = re.search(rf"\b{start}\b", text)
    if not m:
        return ""
    rest = text[m.end():]
    cut = len(rest)
    for e in ends:
        em = re.search(rf"\b{e}\b", rest)
        if em:
            cut = min(cut, em.start())
    return rest[:cut].strip()


def sql_features(sql: str) -> dict:
    """Extract the counts used by the hardness rules."""
    s = _norm(sql)
    set_ops = len(_SET_OPS.findall(_strip_subqueries(s)[0]))
    top, nested = _strip_subqueries(s)
    main = _SET_OPS.split(top)[0]

    select = _clause(main, "select", ["from"]).replace("distinct", "")
    where = _clause(main, "where", ["group by", "order by", "limit", "having"])
    group = _clause(main, "group by", ["order by", "limit", "having"])

    n_join = len(re.findall(r"\bjoin\b", main))
    comp1 = sum(
        [
            bool(where),
            bool(group),
            "order by" in main,
            bool(re.search(r"\blimit\b", main)),
        ]
    ) + n_join + len(re.findall(r"\bor\b", main)) + len(re.findall(r"\blike\b", main))

    comp2 = nested + set_ops

    n_agg = len(_AGG.findall(main))
    sel_cols = len(_split_top_level_commas(select)) if select else 0
    where_conds = 1 + len(re.findall(r"\b(?:and|or)\b", where)) if where else 0
    group_cols = len(_split_top_level_commas(group)) if group else 0
    others = sum([n_agg > 1, sel_cols > 1, where_conds > 1, group_cols > 1])

    return {
        "component1": comp1,
        "component2": comp2,
        "others": others,
        "n_join": n_join,
        "n_agg": n_agg,
        "n_nested": nested,
        "n_set_ops": set_ops,
        "has_group": bool(group),
        "has_order": "order by" in main,
    }


def classify_difficulty(sql: str) -> str:
    """Return one of ``easy / medium / hard / extra`` using Spider's thresholds."""
    f = sql_features(sql)
    c1, c2, o = f["component1"], f["component2"], f["others"]

    if c1 <= 1 and o == 0 and c2 == 0:
        return "easy"
    if (o <= 2 and c1 <= 1 and c2 == 0) or (c1 <= 2 and o < 2 and c2 == 0):
        return "medium"
    if (
        (o > 2 and c1 <= 2 and c2 == 0)
        or (2 < c1 <= 3 and o <= 2 and c2 == 0)
        or (c1 <= 1 and o == 0 and c2 <= 1)
    ):
        return "hard"
    return "extra"
