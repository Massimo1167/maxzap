"""Append rows to a local Excel file."""

from __future__ import annotations

from typing import Any, Dict, List

from openpyxl import load_workbook

from ..core import BaseAction


class ExcelAppendAction(BaseAction):
    """Append data to an Excel workbook."""

    def execute(self, data: Dict[str, Any]) -> None:
        file_path = self.params.get("file")
        sheet_name = self.params.get("sheet")
        fields: List[str] = self.params.get("fields", [])
        if not file_path:
            raise ValueError("file parameter required")
        wb = load_workbook(file_path)
        ws = wb[sheet_name] if sheet_name else wb.active

        if "values" in data:
            values = data["values"]
        else:
            if not fields:
                fields = list(data.keys())
            values = [data.get(f) for f in fields]
        ws.append(values)
        wb.save(file_path)
