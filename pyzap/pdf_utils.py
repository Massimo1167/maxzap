from __future__ import annotations

from typing import Any, Dict, Iterable, List
import re


def extract_table_row(text: str, columns: Iterable[Any]) -> Dict[str, str]:
    """Extract a single row of table data from ``text``.

    ``columns`` may be an iterable of strings or dictionaries with keys:
    ``header`` (header text), ``key`` (output key) and optional ``tokens`` to
    specify how many tokens to assign to the column. Columns can also specify
    ``until_regex`` to capture tokens until a matching pattern is encountered.
    The last column always receives any remaining tokens.
    """

    tokens = re.findall(r"\S+", text.replace("\r", " "))
    if not tokens:
        return {}

    specs: List[Dict[str, Any]] = []
    for col in columns:
        if isinstance(col, str):
            specs.append({"header": col, "key": col, "tokens": None, "until_regex": None})
        else:
            specs.append({
                "header": col.get("header") or col.get("name"),
                "key": col.get("key") or col.get("name"),
                "tokens": col.get("tokens"),
                "until_regex": col.get("until_regex"),
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
            if spec.get("until_regex"):
                pattern = re.compile(spec["until_regex"])
                start = idx
                min_tokens = spec.get("tokens")
                if min_tokens is not None:
                    for _ in range(min_tokens):
                        if idx >= len(value_tokens) or pattern.match(value_tokens[idx]):
                            break
                        idx += 1
                while idx < len(value_tokens) and not pattern.match(value_tokens[idx]):
                    idx += 1
                value = " ".join(value_tokens[start:idx])
            elif spec.get("tokens") is not None:
                tokens = max(0, min(spec["tokens"], remaining))
                value = " ".join(value_tokens[idx : idx + tokens])
                idx += tokens
            else:
                value = " ".join(value_tokens[idx:])
                idx = len(value_tokens)
        else:
            if spec.get("until_regex"):
                pattern = re.compile(spec["until_regex"])
                start = idx
                min_tokens = spec.get("tokens")
                if min_tokens is not None:
                    for _ in range(min_tokens):
                        if idx >= len(value_tokens) or pattern.match(value_tokens[idx]):
                            break
                        idx += 1
                while idx < len(value_tokens) and not pattern.match(value_tokens[idx]):
                    idx += 1
                value = " ".join(value_tokens[start:idx])
            else:
                tokens = spec["tokens"] if spec["tokens"] is not None else 1
                tokens = max(0, min(tokens, remaining))
                value = " ".join(value_tokens[idx : idx + tokens])
                idx += tokens
        result[spec["key"]] = value.replace("\n", " ")

    return result


def parse_invoice_text(text: str) -> Dict[str, Any]:
    """Extract fields from Italian electronic invoice OCR/text `text`.
    Mantiene la stessa interfaccia della versione originale.
    Migliorie:
      - Denominazione (fornitore/cliente) multiline -> robusto a line break OCR.
      - Numero documento -> ignora token di legge (es. 'DPR 633/72').
    """

    def _norm_ws(s: str) -> str:
        return re.sub(r"\s+", " ", s.replace("\r", " ").strip())

    DATE_RE = re.compile(r"\b(\d{4}-\d{2}-\d{2}|\d{2}-\d{2}-\d{4}|\d{2}/\d{2}/\d{4})\b")

    def _to_float(value: str | None) -> float | None:
        if not value:
            return None
        try:
            return float(value.replace(".", "").replace(",", "."))
        except Exception:
            return None

    def _extract_group(pattern: str, src: str,
                       *, flags: int = re.IGNORECASE | re.MULTILINE | re.DOTALL) -> str | None:
        m = re.search(pattern, src, flags)
        return _norm_ws(m.group(1)) if m else None

    def _extract_after_label(block: str, label: str, stops: list[str]) -> str | None:
        """Dopo 'label:' cattura testo anche su più righe fino alla prossima etichetta nota."""
        if not block:
            return None
        m = re.search(label + r"\s*[:\-]?\s*", block, re.IGNORECASE)
        if not m:
            return None
        tail = block[m.end():]
        if not tail:
            return None
        if stops:
            stop_re = re.compile(r"|".join(fr"\b{re.escape(s)}\b" for s in stops), re.IGNORECASE)
            ms = stop_re.search(tail)
            if ms:
                tail = tail[: ms.start()]
        val = _norm_ws(tail).strip()
        return val or None

    clean = "\n".join(_norm_ws(ln) for ln in text.replace("\r", "").splitlines())
    data: Dict[str, Any] = {}

    # ---------------- Fornitore ----------------
    seller_m = re.search(r"Cedente/prestatore\s*\(fornitore\)(.*?)(Cessionario/committente|Tipologia documento)",
                         clean, re.IGNORECASE | re.DOTALL)
    if seller_m:
        sb = seller_m.group(1)
        denom = _extract_group(r"Denominazione\s*[:\-]?\s*(.*?)(?:Comune|Regime fiscale|Indirizzo|Cap|Provincia|Nazione|Telefono|$)", sb)
        if not denom or len(denom) < 5:
            denom = _extract_after_label(sb, "Denominazione",
                                         ["Regime fiscale", "Indirizzo", "Comune", "Provincia", "Cap", "Nazione", "Telefono"])
        data["fornitore"] = {
            "p_iva": _extract_group(r"IVA\s*[:\-]?\s*(\S+)", sb),
            "codice_fiscale": _extract_group(r"Codice fiscale\s*[:\-]?\s*(\S+)", sb),
            "denominazione": denom,
            "regime_fiscale": _extract_group(r"Regime fiscale\s*[:\-]?\s*(.*?)(?:Indirizzo|Comune|Provincia|Cap|Nazione|Telefono|$)", sb),
            "indirizzo": _extract_group(r"Indirizzo\s*[:\-]?\s*(.*?)(?:Comune|Provincia|Cap|Nazione|Telefono|$)", sb),
            "comune": _extract_group(r"Comune\s*[:\-]?\s*(.*?)(?:Provincia|Cap|Nazione|Telefono|$)", sb),
            "provincia": _extract_group(r"Provincia\s*[:\-]?\s*([A-Z]{2})", sb),
            "cap": _extract_group(r"Cap\s*[:\-]?\s*(\d{5})", sb),
            "nazione": _extract_group(r"Nazione\s*[:\-]?\s*(\S+)", sb),
            "telefono": _extract_group(r"Telefono\s*[:\-]?\s*(\S+)", sb),
        }

    # ---------------- Cliente ----------------
    client_m = re.search(r"Cessionario/committente\s*\(cliente\)(.*?)(Tipologia documento|RIEPILOGHI|Cod\.)",
                         clean, re.IGNORECASE | re.DOTALL)
    if client_m:
        cb = client_m.group(1)
        c_denom = _extract_group(r"Denominazione\s*[:\-]?\s*(.*?)(?:Indirizzo|Comune|Provincia|Cap|Nazione|$)", cb)
        if not c_denom or len(c_denom) < 5:
            c_denom = _extract_after_label(cb, "Denominazione",
                                           ["Indirizzo", "Comune", "Provincia", "Cap", "Nazione"])
        data["cliente"] = {
            "p_iva": _extract_group(r"IVA\s*[:\-]?\s*(\S+)", cb),
            "codice_fiscale": _extract_group(r"Codice fiscale\s*[:\-]?\s*(\S+)", cb),
            "denominazione": c_denom,
            "indirizzo": _extract_group(r"Indirizzo\s*[:\-]?\s*(.*?)(?:Comune|Provincia|Cap|Nazione|$)", cb),
            "comune": _extract_group(r"Comune\s*[:\-]?\s*(.*?)(?:Provincia|Cap|Nazione|$)", cb),
            "provincia": _extract_group(r"Provincia\s*[:\-]?\s*([A-Z]{2})", cb),
            "cap": _extract_group(r"Cap\s*[:\-]?\s*(\d{5})", cb),
            "nazione": _extract_group(r"Nazione\s*[:\-]?\s*(\S+)", cb),
        }

    # ---------------- Documento ----------------
    header_m = re.search(r"Tipologia documento(.*?)(?:Cod\.|Prezzo totale|RIEPILOGHI|Totale documento)",
                         clean, re.IGNORECASE | re.DOTALL)
    if header_m:
        hz = _norm_ws(header_m.group(1))
        tokens = re.findall(r"\S+", hz)

        data_doc = None
        date_idx = None
        for i, t in enumerate(tokens):
            if DATE_RE.match(t):
                data_doc = t
                date_idx = i
                break

        def _is_law_token(tok: str) -> bool:
            if "/" in tok and re.fullmatch(r"\d{3}/\d{2}", tok):
                return True
            return tok in {"633/72", "600/73", "600/1973"}

        numero: str | None = None
        if date_idx is not None:
            # cerca un numero valido prima della data (ignorando 'DPR 633/72' e simili)
            i = date_idx - 1
            while i >= 0 and date_idx - i <= 6:
                tok = tokens[i]
                if _is_law_token(tok):
                    i -= 1
                    continue
                if re.fullmatch(r"\d{8,}", tok):  # numero lungo
                    pref = tokens[i-1] if i-1 >= 0 else ""
                    numero = f"{pref} {tok}" if re.fullmatch(r"[A-Za-z0-9]{1,5}-", pref) else tok
                    break
                if re.fullmatch(r"[A-Za-z0-9]{1,5}-\d{3,}", tok):  # prefisso+numero
                    numero = tok
                    break
                if "/" in tok and not _is_law_token(tok) and re.search(r"\d", tok):  # es. 559/M/25
                    numero = tok
                    break
                i -= 1
            if not numero:
                for j in range(date_idx - 1, max(-1, date_idx - 7), -1):
                    tok = tokens[j]
                    if _is_law_token(tok):
                        continue
                    if re.fullmatch(r"\d{6,}", tok):
                        numero = tok
                        break

        tipo = None
        if data_doc:
            tipo = hz.split(numero)[0].strip() if (numero and numero in hz) else hz.split(data_doc)[0].strip()

        codice_dest = None
        if data_doc and date_idx is not None and date_idx + 1 < len(tokens):
            for t in tokens[date_idx + 1:]:
                if re.fullmatch(r"[A-Z0-9]{6,7}", t):
                    codice_dest = t
                    break

        data["documento"] = {
            "tipo": tipo or None,
            "numero": numero,
            "data": data_doc,
            "codice_destinatario": codice_dest,
            "art_73": "Art. 73" if re.search(r"Art\.?\s*73", clean, re.IGNORECASE) else None,
        }

    # ---------------- Righe dettaglio ----------------
    data["righe_dettaglio"] = []
    rows_block = re.search(r"Prezzo totale\n(.*?)RIEPILOGHI IVA E TOTALI", clean, re.DOTALL | re.IGNORECASE)
    if rows_block:
        pattern = re.compile(
            r"^(.*?)\s+"           # descrizione
            r"(\d{1,3}(?:[\.,]\d{1,3})?)\s+"  # quantita
            r"([\d\.,]+)\s+"       # prezzo unitario
            r"([A-Z]{1,3})\s+"     # UM
            r"([\d\.,]+)\s+"       # %IVA
            r"([\d\.,]+)$",        # totale
            re.MULTILINE,
        )
        for m in pattern.finditer(rows_block.group(1)):
            desc, qta, pu, um, iva, tot = m.groups()
            data["righe_dettaglio"].append(
                {
                    "descrizione": desc.strip(),
                    "quantita": _to_float(qta),
                    "prezzo_unitario": _to_float(pu),
                    "unita_misura": um.strip(),
                    "iva_percentuale": _to_float(iva),
                    "prezzo_totale": _to_float(tot),
                }
            )

    # ---------------- Riepilogo importi ----------------
    data["riepilogo_importi"] = {
        "imponibile": _to_float(_extract_group(r"Totale imponibile\s+([\d\.,]+)", clean)),
        "imposta": _to_float(_extract_group(r"Totale imposta\s+([\d\.,]+)", clean)),
        "totale": _to_float(_extract_group(r"Totale documento\s+([\d\.,]+)", clean)),
    }

    # ---------------- Pagamento ----------------
    pay_m = re.search(r"Data scadenza\s+([\d\-/]+)\s+([\d\.,]+)", clean)
    data["pagamento"] = {
        "modalita": _extract_group(r"\bMP\d{2}\s+(\w+)", clean),
        "scadenza": pay_m.group(1) if pay_m else None,
        "importo": _to_float(pay_m.group(2)) if pay_m else None,
    }

    return data
