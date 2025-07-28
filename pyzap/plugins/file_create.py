"""Create a file from the payload."""

from __future__ import annotations

import json
import csv
from pathlib import Path
from typing import Any, Dict, List

from ..core import BaseAction


class FileCreateAction(BaseAction):
    """Write data to a file in various formats."""

    def execute(self, data: Dict[str, Any]) -> None:
        path = self.params.get("path")
        fmt = str(self.params.get("format", "txt")).lower()
        if not path:
            raise ValueError("path required")
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        if fmt == "json":
            p.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        elif fmt == "csv":
            values = data.get("values") or list(data.values())
            with p.open("w", newline="", encoding="utf-8") as fh:
                writer = csv.writer(fh)
                writer.writerow(values)
        else:
            text = str(data.get("text") or data)
            p.write_text(text, encoding="utf-8")
