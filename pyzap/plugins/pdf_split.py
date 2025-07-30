from __future__ import annotations

import os
import re
from typing import Any, Dict, List
from collections import defaultdict


_INVALID_CHARS = re.compile(r'[\\/*?:"<>|]')


def _safe_filename(name: str, max_length: int = 100) -> str:
    """Return a filesystem-safe version of ``name`` limited in length."""
    name = re.sub(r"\s+", " ", name.strip())
    name = _INVALID_CHARS.sub("_", name)
    if len(name) > max_length:
        base, ext = os.path.splitext(name)
        name = base[: max_length - len(ext)] + ext
    return name

from ..core import BaseAction
from ..pdf_utils import extract_table_row


class PDFSplitAction(BaseAction):
    """Split a PDF file into smaller PDFs."""

    def execute(self, data: Dict[str, Any]) -> Dict[str, Any]:
        try:
            from PyPDF2 import PdfReader, PdfWriter  # type: ignore
        except ImportError as exc:  # pragma: no cover - dependency missing
            raise RuntimeError(
                "pdf_split action requires the 'PyPDF2' package. Install it with 'pip install PyPDF2'."
            ) from exc

        pdf_path = data.get("pdf_path")
        if not pdf_path:
            paths = data.get("attachment_paths")
            if paths:
                pdf_path = paths[0]
        output_dir = self.params.get("output_dir")
        pattern = self.params.get("pattern")
        name_template = self.params.get("name_template", "split_{index}.pdf")
        regex_fields: Dict[str, str] = self.params.get("regex_fields", {})
        table_fields = self.params.get("table_fields")

        if not pdf_path:
            raise ValueError("pdf_path parameter required")
        if not output_dir:
            raise ValueError("output_dir parameter required")

        os.makedirs(output_dir, exist_ok=True)

        reader = PdfReader(pdf_path)
        files: List[str] = []
        records: List[Dict[str, Any]] = []

        writer = None
        fields: Dict[str, Any] = {}
        index = 1

        for page in reader.pages:
            text = page.extract_text() or ""
            if pattern and re.search(pattern, text) and writer:
                info = {**data, **fields, "index": index}
                filename = _safe_filename(name_template.format_map(defaultdict(str, info)))
                path = os.path.join(output_dir, filename)
                with open(path, "wb") as fh:
                    writer.write(fh)
                files.append(path)
                records.append({**fields, "file": path})
                writer = None
                fields = {}
                index += 1

            if writer is None:
                writer = PdfWriter()
            writer.add_page(page)

            for key, regex in regex_fields.items():
                if key not in fields:
                    m = re.search(regex, text, re.DOTALL)
                    if m:
                        value = m.group(1) if m.groups() else m.group(0)
                        if isinstance(value, str):
                            value = re.sub(r"\s+", " ", value.strip())
                        fields[key] = value

            if table_fields:
                table_data = extract_table_row(text, table_fields)
                for key, value in table_data.items():
                    if key not in fields:
                        fields[key] = value

        if writer and len(getattr(writer, "pages", [])) > 0:
            info = {**data, **fields, "index": index}
            filename = _safe_filename(name_template.format_map(defaultdict(str, info)))
            path = os.path.join(output_dir, filename)
            with open(path, "wb") as fh:
                writer.write(fh)
            files.append(path)
            records.append({**fields, "file": path})

        data["files"] = files
        if records:
            data["records"] = records
        return data
