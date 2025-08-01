"""Data formatting utilities for PyZap."""

import datetime as _dt
from typing import Any, Dict


def clean_text(text: str) -> str:
    """Remove line breaks and trim whitespace."""
    return " ".join(text.split()).strip()


def parse_date(value: str) -> _dt.datetime:
    """Parse a date string."""
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%d-%m-%Y", "%d/%m/%Y"):
        try:
            return _dt.datetime.strptime(value, fmt)
        except ValueError:
            continue
    raise ValueError(f"Unknown date format: {value}")


def parse_number(value: str) -> float:
    return float(value)


def map_fields(data: Dict[str, Any], mapping: Dict[str, str]) -> Dict[str, Any]:
    return {dest: data.get(src) for src, dest in mapping.items()}


def normalize(data: Dict[str, Any]) -> Dict[str, Any]:
    result = {}
    for k, v in data.items():
        if isinstance(v, str):
            result[k] = clean_text(v)
        else:
            result[k] = v
    return result
