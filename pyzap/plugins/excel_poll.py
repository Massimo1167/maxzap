"""Excel polling trigger."""

from __future__ import annotations

import os
from typing import Any, Dict, List

from ..core import BaseTrigger


class ExcelPollTrigger(BaseTrigger):
    """Poll an Excel workbook for newly appended rows."""

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.state_file = self.config.get("state_file")
        self.start_row = int(self.config.get("start_row", 2))
        self.last_row = self.start_row - 1
        if self.state_file and os.path.exists(self.state_file):
            try:
                with open(self.state_file, "r", encoding="utf-8") as fh:
                    self.last_row = int(fh.read().strip() or self.last_row)
            except Exception:
                pass

    def _save_state(self) -> None:
        if not self.state_file:
            return
        try:
            with open(self.state_file, "w", encoding="utf-8") as fh:
                fh.write(str(self.last_row))
        except Exception:
            pass

    def poll(self) -> List[Dict[str, Any]]:
        try:
            from openpyxl import load_workbook  # type: ignore
        except ImportError as exc:  # pragma: no cover - dependency missing
            raise RuntimeError(
                "excel_poll trigger requires the 'openpyxl' package. Install it with 'pip install openpyxl'."
            ) from exc

        file_path = self.config.get("file")
        sheet_name = self.config.get("sheet")
        filters: Dict[Any, Any] = self.config.get("filters", {})
        if not file_path:
            raise ValueError("file parameter required")

        wb = load_workbook(file_path)
        ws = wb[sheet_name] if sheet_name else wb.active

        max_row = getattr(ws, "max_row", None)
        if max_row is None:
            rows_attr = getattr(ws, "rows", [])
            try:
                max_row = len(list(rows_attr))
            except TypeError:
                max_row = len(rows_attr)

        results: List[Dict[str, Any]] = []
        for row_idx in range(self.last_row + 1, max_row + 1):
            cells = ws[row_idx]
            values = [getattr(c, "value", None) for c in cells]
            match = True
            for col, expected in filters.items():
                idx = int(col) - 1
                val = values[idx] if idx < len(values) else None
                if val != expected:
                    match = False
                    break
            if match:
                results.append({"id": str(row_idx), "values": values})

        self.last_row = max_row
        self._save_state()
        return results
