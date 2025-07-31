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

    The parser is intentionally loose and works with common layout
    variations. Returned data is organised in sections such as
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

    data: Dict[str, Any] = {}

    seller_block = re.search(
        r"Cedente/prestatore \(fornitore\)(.*?)Cessionario/committente",
        text,
        re.DOTALL,
    )
    if seller_block:
        s = seller_block.group(1)
        data["fornitore"] = {
            "p_iva": re.search(r"IVA:\s*(\S+)", s).group(1)
            if re.search(r"IVA:\s*(\S+)", s)
            else None,
            "codice_fiscale": re.search(r"Codice fiscale:\s*(\S+)", s).group(1)
            if re.search(r"Codice fiscale:\s*(\S+)", s)
            else None,
            "denominazione": re.search(r"Denominazione:\s*(.*?)\n", s, re.DOTALL).group(1).strip()
            if re.search(r"Denominazione:\s*(.*?)\n", s, re.DOTALL)
            else None,
            "indirizzo": re.search(r"Indirizzo:\s*(.*?)\n", s, re.DOTALL).group(1).strip()
            if re.search(r"Indirizzo:\s*(.*?)\n", s, re.DOTALL)
            else None,
            "telefono": re.search(r"Telefono:\s*(\S+)", s).group(1)
            if re.search(r"Telefono:\s*(\S+)", s)
            else None,
        }

    client_block = re.search(
        r"Cessionario/committente \(cliente\)(.*?)Tipologia documento",
        text,
        re.DOTALL,
    )
    if client_block:
        c = client_block.group(1)
        denom = re.search(r"Denominazione:(.*?)Indirizzo:", c, re.DOTALL)
        data["cliente"] = {
            "p_iva": re.search(r"IVA:\s*(\S+)", c).group(1)
            if re.search(r"IVA:\s*(\S+)", c)
            else None,
            "codice_fiscale": re.search(r"Codice fiscale:\s*(\S+)", c).group(1)
            if re.search(r"Codice fiscale:\s*(\S+)", c)
            else None,
            "denominazione": " ".join(denom.group(1).split()).strip() if denom else None,
            "indirizzo": re.search(r"Indirizzo:\s*(.*?)\n", c, re.DOTALL).group(1).strip()
            if re.search(r"Indirizzo:\s*(.*?)\n", c, re.DOTALL)
            else None,
        }

    tipo_doc = re.search(r"Tipologia documento(.*?)Art. 73", text, re.DOTALL)
    num_doc = re.search(r"Numero\s*documento(.*?)Data\s*documento", text, re.DOTALL)
    data["documento"] = {
        "tipo": " ".join(tipo_doc.group(1).split()).strip() if tipo_doc else None,
        "numero": " ".join(num_doc.group(1).split()).strip() if num_doc else None,
        "data": re.search(r"Data\s*documento\s*(\S+)", text).group(1).strip()
        if re.search(r"Data\s*documento\s*(\S+)", text)
        else None,
    }

    data["righe_dettaglio"] = []
    rows_block = re.search(
        r"Prezzo totale\n(.*?)RIEPILOGHI IVA E TOTALI",
        text,
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
            re.search(r"Totale imponibile\s+([\d\.,]+)", text).group(1)
            if re.search(r"Totale imponibile\s+([\d\.,]+)", text)
            else None
        ),
        "imposta": _parse_number(
            re.search(r"Totale imposta\s+([\d\.,]+)", text).group(1)
            if re.search(r"Totale imposta\s+([\d\.,]+)", text)
            else None
        ),
        "totale": _parse_number(
            re.search(r"Totale documento\s+([\d\.,]+)", text).group(1)
            if re.search(r"Totale documento\s+([\d\.,]+)", text)
            else None
        ),
    }

    pay_match = re.search(r"Data scadenza\s+([\d-]+)\s+([\d\.,]+)", text)
    data["pagamento"] = {
        "modalita": re.search(r"MP\d{2}\s+(\w+)", text).group(1).strip()
        if re.search(r"MP\d{2}\s+(\w+)", text)
        else None,
        "scadenza": pay_match.group(1) if pay_match else None,
        "importo": _parse_number(pay_match.group(2)) if pay_match else None,
    }

    return data
