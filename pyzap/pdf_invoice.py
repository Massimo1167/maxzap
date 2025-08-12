from __future__ import annotations

from typing import Any, Dict, Iterable, List
import re
import os
import difflib


def _read_tipologie_known() -> List[str]:
    """Legge tutti i codici TD dal file TDxx fattura.help"""
    try:
        # Cerca il file nella directory parent
        current_dir = os.path.dirname(os.path.abspath(__file__))
        parent_dir = os.path.dirname(current_dir)
        file_path = os.path.join(parent_dir, "TDxx fattura.help")
        
        if os.path.exists(file_path):
            with open(file_path, "r", encoding="utf-8") as f:
                lines = [line.strip() for line in f if line.strip()]
                return lines
    except Exception:
        pass
    
    # Fallback con TUTTI i termini TD dal file "TDxx fattura.help"
    return [
        "TD01 Fattura",
        "TD02 Acconto/anticipo su fattura",
        "TD03 Acconto/anticipo su parcella",
        "TD04 Nota di credito",
        "TD05 Nota di debito",
        "TD06 Parcella",
        "TD07 Fattura semplificata",
        "TD08 Nota di credito semplificata",
        "TD09 Nota di debito semplificata",
        "TD10 Fattura differita (ex art. 21 comma 4 DPR 633/72)",
        "TD11 Fattura per acquisto intracomunitario",
        "TD12 Documento di trasporto (DDT)",
        "TD13 Ricevuta fiscale",
        "TD14 Fattura riepilogativa (per regolarizzazione o rettifica)",
        "TD15 Integrazione fattura reverse charge interno",
        "TD16 Integrazione fattura reverse charge esterno/UE",
        "TD17 Integrazione/autofattura per acquisto servizi dall'estero",
        "TD18 Integrazione/autofattura per acquisto di beni intracomunitari",
        "TD19 Integrazione/autofattura per acquisto di beni ex art. 17 c.2 DPR 633/72",
        "TD20 Autofattura per regolarizzazione e integrazione delle fatture (ex art. 6 c. 8 d.lgs. 471/97 o art. 46 c.5 D.L. 331/93)",
        "TD21 Autofattura per splafonamento",
        "TD22 Estrazione beni da Deposito IVA",
        "TD23 Estrazione beni da Deposito IVA con versamento dell'IVA",
        "TD24 fattura differita di cui all'art.21, comma 4, terzo periodo lett.a) DPR 633/72",
        "TD25 Fattura differita di cui all'art.21, comma 4, terzo periodo lett.b) DPR 633/72",
        "TD26 Cessione di beni ammortizzabili e per passaggi interni (ex art. 36 DPR 633/72)",
        "TD27 Fattura per autoconsumo o per cessioni gratuite senza rivalsa",
        "TD28 Acquisti da San Marino con IVA (fattura cartacea)",
        "TD29 Comunicazione per omessa o irregolare fatturazione (introdotto dal 1° aprile 2025)",
    ]


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

    # ---------------- Documento (MIGLIORATO: include righe multi-line TD) ----------------
    header_m = re.search(r"Tipologia documento(.*?)(?:Cod\.|Prezzo totale|RIEPILOGHI|Totale documento)",
                         clean, re.IGNORECASE | re.DOTALL)
    if header_m:
        hz = header_m.group(1)
        
        # MODIFICA CHIAVE: Non rimuove più le righe TD - le include nel testo per il parsing
        # Rimuove solo pattern header specifici ma conserva i dati TD
        lines = hz.split('\n')
        cleaned_lines = []
        
        for line in lines:
            line_clean = line.strip()
            if not line_clean:
                continue
                
            # Rimuove solo righe che sono puramente header (senza dati)
            if re.match(r"^(?:Art\.?\s*73\s*|Numero\s+documento\s*|Data\s+documento\s*|Codice\s+destinatario\s*)$", line_clean, re.IGNORECASE):
                continue
                
            # INCLUDE righe che contengono TD o dati documento
            if (re.search(r"\bTD\d{2}\b", line_clean, re.IGNORECASE) or  # Righe con codici TD
                re.search(r"\d{2,4}[-/]\d{1,2}[-/]\d{2,4}", line_clean) or  # Date
                re.search(r"\b[A-Z0-9]{6,7}\b", line_clean) or  # Codici destinatario 
                re.search(r"\bDPR\s+\d+/\d+\b", line_clean, re.IGNORECASE) or  # Pattern DPR
                re.search(r"^\d+$", line_clean) or  # Righe con solo numeri (numero documento)
                (len(line_clean.split()) >= 2 and re.search(r"\d", line_clean))):  # Righe con dati numerici
                cleaned_lines.append(line_clean)
        
        # Combina tutte le righe di dati
        hz_clean = " ".join(cleaned_lines)
        tokens = re.findall(r"\S+", hz_clean)

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

        # ESTRAZIONE NUMERO CON STRATEGIA MIGLIORATA (date-anchored approach)
        numero: str | None = None
        if date_idx is not None:
            # STRATEGIA MIGLIORATA: Il numero documento è immediatamente prima della data
            # Cerca nell'intero testo il pattern: [qualsiasi_cosa] [NUMERO] [DATA]
            
            # Metodo 1: Trova il token immediatamente prima della data
            if date_idx > 0:
                potential_numero = tokens[date_idx - 1]
                # Verifica che non sia parte della tipologia (evita DPR, 633/72, ecc.)
                if (not re.search(r"^(DPR|lett\.|a\)|b\)|c\))$", potential_numero, re.IGNORECASE) and
                   not re.search(r"^\d{3}/\d{2}$", potential_numero) and
                   potential_numero not in ["DPR", "633/72"] and
                   not _is_law_token(potential_numero)):  # Non DPR 633/72
                    numero = potential_numero
            
            # Metodo 2 (fallback): Cerca pattern numerici prima della data nel testo
            if not numero:
                text_before_date = " ".join(tokens[:date_idx])
                # Trova ultimo numero o codice alfanumerico prima della data
                matches = re.findall(r'\b([A-Z]{1,4}[-\s]*\d+(?:/\d+)?|\d+(?:/\d+)?)\b', text_before_date)
                if matches:
                    # Prende l'ultimo match che non è DPR 633/72
                    for match in reversed(matches):
                        if not re.match(r'^\d{3}/\d{2}$', match):  # Non DPR 633/72
                            numero = match
                            break
            
            # Metodo 3 (fallback): logica originale come ultima risorsa
            if not numero:
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

        # ESTRAZIONE TIPOLOGIA CON APPROCCIO TD-BASED (portato da OCR version)
        tipo = None
        if tokens and data_doc:
            # Trova il primo codice TD nei token prima della data usando fuzzy matching
            tipologie_note = _read_tipologie_known()
            tipo_found = None
            
            # Cerca il codice TD più lungo che matcha
            date_idx_search = date_idx if date_idx is not None else len(tokens)
            remaining_tokens = tokens[:date_idx_search]  # Tutti i token prima della data
            remaining_text = " ".join(remaining_tokens)
            
            for td_full in tipologie_note:
                td_code = td_full[:4]  # Es: "TD24"
                
                # METODO 1: Cerca il codice TD esplicito nei token
                td_explicit_found = False
                for i in range(date_idx_search):
                    if tokens[i].upper().startswith(td_code):
                        # Match fuzzy con la tipologia completa
                        similarity = difflib.SequenceMatcher(None, 
                                                           remaining_text.lower(), 
                                                           td_full.lower()).ratio()
                        
                        if similarity > 0.5:  # Soglia di similarità
                            if not tipo_found or similarity > tipo_found[1]:
                                tipo_found = (td_full, similarity, i)
                                td_explicit_found = True
                
                # METODO 2: Se non trova TD esplicito, cerca parti significative del testo
                if not td_explicit_found:
                    # Estrae parti significative dalla definizione TD (dopo le prime 3 parole)
                    td_parts = td_full.split()[3:]  # Salta "TD24 fattura differita"
                    if td_parts:
                        td_significant = " ".join(td_parts)
                        
                        # Match fuzzy con la parte significativa  
                        similarity = difflib.SequenceMatcher(None, 
                                                           remaining_text.lower(), 
                                                           td_significant.lower()).ratio()
                        
                        if similarity > 0.7:  # Soglia più alta per match parziali
                            if not tipo_found or similarity > tipo_found[1]:
                                tipo_found = (td_full, similarity, 0)
            
            if tipo_found:
                tipo = tipo_found[0]  # Usa la tipologia completa dai TD noti
            else:
                # Fallback: usa la versione precedente
                if date_idx is not None:
                    end_idx = date_idx
                    if numero:
                        numero_tokens = numero.split()
                        for i in range(len(tokens) - len(numero_tokens) + 1):
                            if tokens[i:i+len(numero_tokens)] == numero_tokens:
                                end_idx = i
                                break
                    tipo_tokens = tokens[:end_idx]
                    tipo = " ".join(tipo_tokens).strip()
                else:
                    tipo = " ".join(tokens).strip()

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
