from __future__ import annotations

from typing import Any, Dict, Iterable, List
import re


def extract_table_row(text: str, columns: Iterable[Any]) -> Dict[str, str]:
    """Extract a single row of table data from ``text``.

    ``columns`` may be an iterable of strings or dictionaries with keys:
    ``header`` (header text), ``key`` (output key) and optional ``tokens`` to
    specify how many tokens to assign to the column. The last column always
    receives any remaining tokens.
    """

    tokens = re.findall(r"\S+", text.replace("\r", " "))
    if not tokens:
        return {}

    specs: List[Dict[str, Any]] = []
    for col in columns:
        if isinstance(col, str):
            specs.append({"header": col, "key": col, "tokens": None})
        else:
            specs.append({
                "header": col.get("header") or col.get("name"),
                "key": col.get("key") or col.get("name"),
                "tokens": col.get("tokens"),
            })

    headers = [s["header"] for s in specs]
    header_tokens: List[str] = []
    for h in headers:
        header_tokens.extend(h.split())

    header_tokens_lower = [t.lower() for t in header_tokens]
    tokens_lower = [t.lower() for t in tokens]
    header_idx = None
    for i in range(len(tokens_lower) - len(header_tokens_lower) + 1):
        if tokens_lower[i : i + len(header_tokens_lower)] == header_tokens_lower:
            header_idx = i
            break
    if header_idx is None or header_idx + len(header_tokens) >= len(tokens):
        return {}

    value_tokens = tokens[header_idx + len(header_tokens) :]
    result: Dict[str, str] = {}
    idx = 0
    for j, spec in enumerate(specs):
        remaining = len(value_tokens) - idx
        if remaining <= 0:
            value = ""
        elif j == len(specs) - 1:
            value = " ".join(value_tokens[idx:])
            idx = len(value_tokens)
        else:
            tokens = spec["tokens"] if spec["tokens"] is not None else 1
            tokens = max(0, min(tokens, remaining))
            value = " ".join(value_tokens[idx : idx + tokens])
            idx += tokens
        result[spec["key"]] = value.replace("\n", " ")

    return result


def parse_invoice_text(text: str) -> Dict[str, Any]:
    """Extract fields from Italian electronic invoice OCR ``text``.

    The original implementation relied on very strict regular
    expressions which often failed with noisy OCR output.  The parser
    now normalises whitespace and searches the relevant blocks using
    case-insensitive patterns making it much more tolerant of layout
    variations.  Returned data is organised in sections such as
    ``fornitore`` (seller), ``cliente`` (buyer), ``documento`` and so on.
    Missing values are returned as ``None``.
    """

    def _parse_number(value: str | None) -> float | str | None:
        if not value:
            return None
        try:
            return float(value.replace(".", "").replace(",", "."))
        except (ValueError, AttributeError):
            return value

    clean_text = text.replace("\r", "")
    lines = [re.sub(r"\s+", " ", ln.strip()) for ln in clean_text.splitlines()]
    normalised = "\n".join(lines)

    def _extract(pattern: str, src: str = normalised) -> str | None:
        m = re.search(pattern, src, re.IGNORECASE | re.MULTILINE)
        if not m:
            return None
        return " ".join(m.group(1).split()).strip()

    def _block(start: str, end: str) -> str | None:
        m = re.search(start + r"(.*?)" + end, normalised, re.IGNORECASE | re.DOTALL)
        return m.group(1) if m else None

    data: Dict[str, Any] = {}

    seller_chunk = _block(r"Cedente/prestatore\s*\(fornitore\)", r"Cessionario/committente")
    if seller_chunk:
        data["fornitore"] = {
            "p_iva": _extract(r"IVA\s*[:\-]?\s*(\S+)", seller_chunk),
            "codice_fiscale": _extract(r"Codice fiscale\s*[:\-]?\s*(\S+)", seller_chunk),
            "denominazione": _extract(r"Denominazione\s*[:\-]?\s*(.*?)(?:\n|$)", seller_chunk),
            "indirizzo": _extract(r"Indirizzo\s*[:\-]?\s*(.*?)(?:\n|$)", seller_chunk),
            "telefono": _extract(r"Telefono\s*[:\-]?\s*(\S+)", seller_chunk),
        }

    client_chunk = _block(r"Cessionario/committente\s*\(cliente\)", r"Tipologia documento")
    if client_chunk:
        data["cliente"] = {
            "p_iva": _extract(r"IVA\s*[:\-]?\s*(\S+)", client_chunk),
            "codice_fiscale": _extract(r"Codice fiscale\s*[:\-]?\s*(\S+)", client_chunk),
            "denominazione": _extract(r"Denominazione\s*[:\-]?\s*(.*?)(?:Indirizzo|\n|$)", client_chunk),
            "indirizzo": _extract(r"Indirizzo\s*[:\-]?\s*(.*?)(?:\n|$)", client_chunk),
        }

    tipo_doc = re.search(r"Tipologia documento\s*(.*?)\n", normalised, re.IGNORECASE)
    num_doc = re.search(r"Numero\s*documento\s*(.*?)\n", normalised, re.IGNORECASE)
    data["documento"] = {
        "tipo": " ".join(tipo_doc.group(1).split()).strip() if tipo_doc else None,
        "numero": " ".join(num_doc.group(1).split()).strip() if num_doc else None,
        "data": _extract(r"Data\s*documento\s*(\S+)")
    }

    data["righe_dettaglio"] = []
    rows_block = re.search(
        r"Prezzo totale\n(.*?)RIEPILOGHI IVA E TOTALI",
        normalised,
        re.DOTALL,
    )
    if rows_block:
        pattern = re.compile(
            r"^(.*?)\s+"  # descrizione
            r"(\d{1,},\d{2})\s+"  # quantita
            r"([\d\.,]+)\s+"  # prezzo unitario
            r"(\w{2})\s+"  # unita
            r"([\d\.,]+)\s+"  # iva
            r"([\d\.,]+)$",
            re.MULTILINE,
        )
        for m in pattern.finditer(rows_block.group(1)):
            desc, qta, pu, um, iva, tot = m.groups()
            data["righe_dettaglio"].append(
                {
                    "descrizione": desc.strip(),
                    "quantita": _parse_number(qta),
                    "prezzo_unitario": _parse_number(pu),
                    "unita_misura": um.strip(),
                    "iva_percentuale": _parse_number(iva),
                    "prezzo_totale": _parse_number(tot),
                }
            )

    data["riepilogo_importi"] = {
        "imponibile": _parse_number(
            re.search(r"Totale imponibile\s+([\d\.,]+)", normalised).group(1)
            if re.search(r"Totale imponibile\s+([\d\.,]+)", normalised)
            else None
        ),
        "imposta": _parse_number(
            re.search(r"Totale imposta\s+([\d\.,]+)", normalised).group(1)
            if re.search(r"Totale imposta\s+([\d\.,]+)", normalised)
            else None
        ),
        "totale": _parse_number(
            re.search(r"Totale documento\s+([\d\.,]+)", normalised).group(1)
            if re.search(r"Totale documento\s+([\d\.,]+)", normalised)
            else None
        ),
    }

    pay_match = re.search(r"Data scadenza\s+([\d-]+)\s+([\d\.,]+)", normalised)
    data["pagamento"] = {
        "modalita": _extract(r"MP\d{2}\s+(\w+)"),
        "scadenza": pay_match.group(1) if pay_match else None,
        "importo": _parse_number(pay_match.group(2)) if pay_match else None,
    }

    return data
