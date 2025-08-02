"""Append rows to a local Excel file."""

from __future__ import annotations

import json
import email.utils
from typing import Any, Dict, List



from ..core import BaseAction
from ..utils import excel_lock


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
        max_message_length = self.params.get("max_message_length")
        if max_message_length is not None:
            try:
                max_message_length = int(max_message_length)
            except Exception:
                max_message_length = None
        message_fields = {"summary", "body", "message"}
        if not file_path:
            raise ValueError("file parameter required")
        keep_vba = str(file_path).lower().endswith(".xlsm")

        with excel_lock(file_path):
            wb = load_workbook(file_path, keep_vba=keep_vba)
            try:
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
                    if isinstance(value, str) and name in message_fields and max_message_length:
                        value = value[:max_message_length]
                    if name == "datetime" and isinstance(value, str):
                        try:
                            dt = email.utils.parsedate_to_datetime(value)
                            value = dt.strftime("%d/%m/%Y %H:%M:%S")
                        except Exception:
                            pass
                    if name == "attachments" and isinstance(value, (list, tuple)):
                        return "; ".join(str(v) for v in value)
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
            finally:
                getattr(getattr(wb, "vba_archive", None), "close", lambda: None)()
                getattr(wb, "close", lambda: None)()
