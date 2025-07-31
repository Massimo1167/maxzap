"""Utility per testare la funzione ``parse_invoice_text``.

Esempio:
    python parse_invoice_cli.py FATTURA.pdf
"""

import json
import sys
from PyPDF2 import PdfReader

from pyzap.pdf_utils import parse_invoice_text


def parse_pdf(path: str) -> dict:
    """Estrae il testo dal PDF e restituisce i dati di parse_invoice_text."""
    reader = PdfReader(path)
    text = "".join(page.extract_text() or "" for page in reader.pages)
    return parse_invoice_text(text)


def main(argv: list[str]) -> None:
    if len(argv) < 2:
        print("Uso: python parse_invoice_cli.py <file.pdf> [altri.pdf ...]")
        raise SystemExit(1)
    for fname in argv[1:]:
        print(f"\n--- {fname} ---")
        result = parse_pdf(fname)
        print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main(sys.argv)
