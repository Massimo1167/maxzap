"""Append rows to a local Excel file."""

from __future__ import annotations

import json
from typing import Any, Dict, List



from ..core import BaseAction


class ExcelAppendAction(BaseAction):
    """Append data to an Excel workbook."""

    def execute(self, data: Dict[str, Any]) -> None:
        try:
            from openpyxl import load_workbook  # type: ignore
        except ImportError as exc:  # pragma: no cover - dependency missing
            raise RuntimeError(
                "excel_append action requires the 'openpyxl' package. "
                "Install it with 'pip install openpyxl'."
            ) from exc

        file_path = self.params.get("file")
        sheet_name = self.params.get("sheet")
        fields: List[str] = self.params.get("fields", [])
        if not file_path:
            raise ValueError("file parameter required")
        wb = load_workbook(file_path)
        ws = wb[sheet_name] if sheet_name else wb.active

        if "values" in data:
            values = data["values"]
            field_names = [str(i) for i in range(len(values))]
        else:
            if not fields:
                fields = list(data.keys())
            field_names = fields
            values = [data.get(f) for f in fields]

        def _convert(value: Any, name: str) -> Any:
            if name == "storage_path" and not value:
                return None
            if isinstance(value, (list, tuple)):
                return ", ".join(str(v) for v in value)
            if isinstance(value, dict):
                return json.dumps(value, ensure_ascii=False)
            return value

        row = [_convert(v, n) for v, n in zip(values, field_names)]
        exists = False
        try:
            rows = getattr(ws, "rows", None)
            if rows is not None:
                if row in list(rows):
                    exists = True
            else:
                for existing in ws.values:
                    if list(existing)[: len(row)] == row:
                        exists = True
                        break
        except Exception:
            pass

        if not exists:
            ws.append(row)
            wb.save(file_path)
