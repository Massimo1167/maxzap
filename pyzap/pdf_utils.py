from __future__ import annotations

from typing import Any, Dict, Iterable, List


def extract_table_row(text: str, columns: Iterable[Any]) -> Dict[str, str]:
    """Extract a single row of table data from ``text``.

    ``columns`` may be an iterable of strings or dictionaries with keys:
    ``header`` (header text), ``key`` (output key) and optional ``tokens`` to
    specify how many tokens to assign to the column. The last column always
    receives any remaining tokens.
    """

    lines = [l.strip() for l in text.replace("\r", "").split("\n") if l.strip()]
    if len(lines) < 2:
        return {}

    specs: List[Dict[str, Any]] = []
    for col in columns:
        if isinstance(col, str):
            specs.append({"header": col, "key": col, "tokens": None})
        else:
            specs.append({
                "header": col.get("header") or col.get("name"),
                "key": col.get("key") or col.get("name"),
                "tokens": col.get("tokens"),
            })

    headers = [s["header"] for s in specs]
    header_idx = None
    for i, line in enumerate(lines[:-1]):
        if all(h and h.lower() in line.lower() for h in headers):
            header_idx = i
            break
    if header_idx is None or header_idx + 1 >= len(lines):
        return {}

    value_tokens = lines[header_idx + 1].split()
    result: Dict[str, str] = {}
    idx = 0
    for j, spec in enumerate(specs):
        remaining = len(value_tokens) - idx
        if remaining <= 0:
            value = ""
        elif j == len(specs) - 1:
            value = " ".join(value_tokens[idx:])
            idx = len(value_tokens)
        else:
            tokens = spec["tokens"] if spec["tokens"] is not None else 1
            tokens = max(0, min(tokens, remaining))
            value = " ".join(value_tokens[idx : idx + tokens])
            idx += tokens
        result[spec["key"]] = value

    return result
