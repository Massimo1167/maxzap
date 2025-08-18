from __future__ import annotations

import os
import re
from collections import defaultdict
from typing import Any, Dict, List

from ..core import BaseAction
from ..pdf_invoice import extract_table_row, parse_invoice_text
from ..formatter import parse_date
from ..utils import safe_filename

# Importa pdfminer per estrazione testo migliorata
try:
    from pdfminer.high_level import extract_text
    PDFMINER_AVAILABLE = True
except ImportError:
    PDFMINER_AVAILABLE = False


def _flatten_dict(data: Dict[str, Any], prefix: str = "") -> Dict[str, Any]:
    """Return a flat dict joining nested keys with underscores."""
    flat: Dict[str, Any] = {}
    for key, value in data.items():
        new_key = f"{prefix}{key}"
        if isinstance(value, dict):
            flat.update(_flatten_dict(value, new_key + "_"))
        else:
            flat[new_key] = value
    return flat


def _extract_text_from_writer(writer, pdf_path: str, temp_dir: str) -> str:
    """Estrae testo dal PdfWriter usando pdfminer per parsing accurato"""
    if not PDFMINER_AVAILABLE:
        # Fallback: estrai testo dalle pagine del writer usando PyPDF2
        full_text = ""
        for page in writer.pages:
            full_text += page.extract_text() or ""
        return full_text
    
    # Usa pdfminer: salva temporaneamente il PDF e leggi con pdfminer
    import tempfile
    try:
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False, dir=temp_dir) as temp_file:
            writer.write(temp_file)
            temp_path = temp_file.name
        
        # Estrai con pdfminer
        text = extract_text(temp_path)
        
        # Rimuovi file temporaneo
        try:
            os.unlink(temp_path)
        except Exception:
            pass
            
        return text
    except Exception:
        # Fallback a PyPDF2 se c'è un errore
        full_text = ""
        for page in writer.pages:
            full_text += page.extract_text() or ""
        return full_text


class SplitInvoicePdfAction(BaseAction):
    """Split a PDF file into smaller PDFs."""

    def execute(self, data: Dict[str, Any]) -> Dict[str, Any]:
        try:
            from PyPDF2 import PdfReader, PdfWriter  # type: ignore
        except ImportError as exc:  # pragma: no cover - dependency missing
            raise RuntimeError(
                "split_invoice_pdf action requires the 'PyPDF2' package. Install it with 'pip install PyPDF2'."
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
        parse_invoice = bool(self.params.get("parse_invoice"))
        date_formats: Dict[str, str] = self.params.get("date_formats", {})

        if not pdf_path:
            raise ValueError("pdf_path parameter required")
        if not output_dir:
            raise ValueError("output_dir parameter required")

        os.makedirs(output_dir, exist_ok=True)

        files: List[str] = []
        records: List[Dict[str, Any]] = []

        writer = None
        fields: Dict[str, Any] = {}
        index = 1
        chunk_text = ""

        # Ensure the PDF file handle is properly closed after processing
        with open(pdf_path, "rb") as fh:
            reader = PdfReader(fh)
            for page in reader.pages:
                text = page.extract_text() or ""
                if pattern and re.search(pattern, text) and writer:
                    invoice_data = None
                    if parse_invoice:
                        # TEMPORANEO: torna al comportamento originale per evitare regressioni
                        invoice_data = parse_invoice_text(chunk_text)
                        flat = _flatten_dict(invoice_data)
                        for k, v in flat.items():
                            if k in date_formats and isinstance(v, str):
                                try:
                                    v = parse_date(v).strftime(date_formats[k])
                                except Exception:
                                    pass
                            fields.setdefault(k, v)
                    info = {**data, **fields, "index": index}
                    filename = safe_filename(name_template.format_map(defaultdict(str, info)))
                    path = os.path.join(output_dir, filename)
                    with open(path, "wb") as out_fh:
                        writer.write(out_fh)
                    record = {**fields, "file": path}
                    if invoice_data is not None:
                        record["invoice"] = invoice_data
                    files.append(path)
                    records.append(record)
                    writer = None
                    fields = {}
                    chunk_text = ""
                    index += 1

                if writer is None:
                    writer = PdfWriter()
                writer.add_page(page)
                chunk_text += text

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
            invoice_data = None
            if parse_invoice:
                invoice_data = parse_invoice_text(chunk_text)
                flat = _flatten_dict(invoice_data)
                for k, v in flat.items():
                    if k in date_formats and isinstance(v, str):
                        try:
                            v = parse_date(v).strftime(date_formats[k])
                        except Exception:
                            pass
                    fields.setdefault(k, v)
            info = {**data, **fields, "index": index}
            filename = safe_filename(name_template.format_map(defaultdict(str, info)))
            path = os.path.join(output_dir, filename)
            with open(path, "wb") as out_fh:
                writer.write(out_fh)
            record = {**fields, "file": path}
            if invoice_data is not None:
                record["invoice"] = invoice_data
            files.append(path)
            records.append(record)

        data["files"] = files
        if records:
            data["records"] = records
        return data
