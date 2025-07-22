"""Utility functions for text and date formatting."""

from datetime import datetime
from typing import Any, Dict, Optional


def clean_text(text: str) -> str:
    """Return a sanitized string.

    TODO: implement text cleaning logic
    """
    return text.strip()


def parse_date(value: str, fmt: str = "%Y-%m-%d") -> Optional[datetime]:
    """Parse date from string.

    TODO: support more date formats and error handling
    """
    try:
        return datetime.strptime(value, fmt)
    except (TypeError, ValueError):
        return None


def map_fields(data: Dict[str, Any], mapping: Dict[str, str]) -> Dict[str, Any]:
    """Map dictionary keys based on a mapping table.

    TODO: expand this helper with complex mapping rules
    """
    return {mapping.get(k, k): v for k, v in data.items()}
