from __future__ import annotations

from typing import Any, Dict, List

from ..core import BaseAction
from ..pdf_utils import parse_invoice_text
from ..utils import excel_lock


class InvoiceExcelAppendAction(BaseAction):
    """Append parsed invoice data to an Excel workbook."""

    def execute(self, data: Dict[str, Any]) -> None:
        try:
            from openpyxl import load_workbook  # type: ignore
        except ImportError as exc:  # pragma: no cover - dependency missing
            raise RuntimeError(
                "invoice_excel_append action requires the 'openpyxl' package. "
                "Install it with 'pip install openpyxl'."
            ) from exc

        text = data.get("text")
        pdf_path = data.get("pdf_path")
        if text is None and pdf_path:
            try:
                from PyPDF2 import PdfReader  # type: ignore
            except ImportError as exc:  # pragma: no cover - dependency missing
                raise RuntimeError(
                    "invoice_excel_append action requires the 'PyPDF2' package. "
                    "Install it with 'pip install PyPDF2'."
                ) from exc
            reader = PdfReader(pdf_path)
            text = "\n".join(page.extract_text() or "" for page in reader.pages)

        if text is None:
            raise ValueError("text or pdf_path required")

        inv = parse_invoice_text(text)

        def _flatten(prefix: str, value: Any, out: Dict[str, Any]) -> None:
            if isinstance(value, dict):
                for k, v in value.items():
                    _flatten(f"{prefix}_{k}" if prefix else k, v, out)
            elif isinstance(value, list):
                out[prefix] = str(value)
            else:
                out[prefix] = value

        flat: Dict[str, Any] = {}
        _flatten("", inv, flat)

        fields: List[str] = self.params.get("fields", [])
        values = [flat.get(f) for f in fields] if fields else list(flat.values())

        file_path = self.params.get("file")
        sheet_name = self.params.get("sheet")
        if not file_path:
            raise ValueError("file parameter required")

        keep_vba = str(file_path).lower().endswith(".xlsm")
        with excel_lock(file_path):
            wb = load_workbook(file_path, keep_vba=keep_vba)
            ws = wb[sheet_name] if sheet_name else wb.active
            ws.append(values)
            wb.save(file_path)
