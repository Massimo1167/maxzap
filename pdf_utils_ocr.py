from typing import Any, Dict, Iterable, List, Tuple
import re
import difflib
import os

# ==============================
# Nuovo parser OCR: pdf_utils_ocr.py
# - NON tocca pdf_invoice.py (legacy)
# - parse_invoice_text: stessa interfaccia, ma aggiunge "debug_header" nel dict
# - CLI: scrive CSV con separatore ; e flag --debug-headers / --compare-native
# ==============================

# ------------------------------
# Funzioni di supporto
# ------------------------------

def extract_table_row(text: str, columns: Iterable[Any]) -> Dict[str, str]:
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
                tokens_take = max(0, min(spec["tokens"], remaining))
                value = " ".join(value_tokens[idx : idx + tokens_take])
                idx += tokens_take
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
                tokens_take = spec["tokens"] if spec["tokens"] is not None else 1
                tokens_take = max(0, min(tokens_take, remaining))
                value = " ".join(value_tokens[idx : idx + tokens_take])
                idx += tokens_take
        result[spec["key"]] = value.replace("\n", " ")
    return result


def _norm_ws(s: str) -> str:
    return re.sub(r"\s+", " ", s.replace("\r", " ").strip())


def _to_float(value: str | None) -> float | None:
    if not value:
        return None
    try:
        return float(value.replace(".", "").replace(",", "."))
    except Exception:
        return None


DATE_RE = re.compile(r"\b(\d{4}-\d{2}-\d{2}|\d{2}-\d{2}-\d{4}|\d{2}/\d{2}/\d{4})\b")


def _extract_group(pattern: str, src: str, *, flags: int = re.IGNORECASE | re.MULTILINE | re.DOTALL) -> str | None:
    m = re.search(pattern, src, flags)
    return _norm_ws(m.group(1)) if m else None


def _read_tipologie_known() -> List[str]:
    """Carica le tipologie documento predefinite dal file di help."""
    help_file = "TDxx fattura.help"
    
    if os.path.exists(help_file):
        try:
            with open(help_file, "r", encoding="utf-8") as f:
                lines = []
                for line in f:
                    line = line.strip()
                    if line and re.match(r"^TD\d{2}\s+", line):
                        lines.append(line)
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


LAW_TOKENS = {"633/72", "600/73", "600/1973"}


def _is_law_token(tok: str) -> bool:
    if "/" in tok and re.fullmatch(r"\d{3}/\d{2}", tok):
        return True
    return tok in LAW_TOKENS or (tok.upper().startswith("DPR") and "633/72" in tok)


def _looks_like_cod_dest(tok: str) -> bool:
    return bool(re.fullmatch(r"[A-Z0-9]{6,7}", tok))


def _cleanup_tok(tok: str) -> str:
    tok = tok.strip().strip(".,;:()[]{}")
    tok = re.sub(r"[^A-Za-z0-9/\-]", "", tok)
    return tok


def _score_docnum(tok: str) -> int:
    if _looks_like_cod_dest(tok) or _is_law_token(tok):
        return -10
    s = 0
    digits = sum(ch.isdigit() for ch in tok)
    s += min(digits, 12)
    if "-" in tok:
        s += 2
    if "/" in tok and not _is_law_token(tok):
        s += 1
    if re.search(r"[A-Za-z]", tok):
        s += 1
    if len(tok) >= 9:
        s += 2
    return s


# ------------------------------
# Header DOCUMENTO (1 o 2 righe) + debug
# ------------------------------

HEADER_LABELS = ["Tipologia documento", "Art. 73", "Numero documento", "Data documento", "Codice destinatario"]
# Varianti tollerate per header multi-riga (ogni parte può essere su righe separate)
HEADER_VARIANTS = {
    "Tipologia documento": [
        r"Tipologia\s+documento",  # riga singola
        r"Tipologia.*?documento",  # multi-riga con wildcard
    ],
    "Art. 73": [r"Art\.?\s*73"],
    "Numero documento": [
        r"Numero\s+documento",     # riga singola
        r"N\.?\s*documento", 
        r"Numero\s+doc\.?",
        r"Numero.*?documento",     # multi-riga: "Numero" + qualsiasi cosa + "documento"
    ],
    "Data documento": [
        r"Data\s+documento",       # riga singola
        r"Data\s+doc\.?",
        r"Data.*?documento",       # multi-riga: "Data" + qualsiasi cosa + "documento"
    ],
    "Codice destinatario": [
        r"Cod(?:ice)?\s+destinatario", 
        r"Cod\.\s*destinatario",
        r"Codice.*?destinatario",  # multi-riga: "Codice" + qualsiasi cosa + "destinatario"
        r"Cod\..*?destinatario",   # multi-riga: "Cod." + qualsiasi cosa + "destinatario"
    ],
}

# Pattern per identificare parti di header che potrebbero essere distribuite su più righe
HEADER_PARTS = {
    "Numero documento": ["Numero", "documento"],
    "Data documento": ["Data", "documento"], 
    "Codice destinatario": ["Codice", "destinatario", "Cod.", "Cod"],
}


def _label_found(blob: str, canonical: str) -> bool:
    """Verifica se un'etichetta header è presente nel blob di testo."""
    patterns = HEADER_VARIANTS.get(canonical, [re.escape(canonical)])
    for pat in patterns:
        if re.search(pat, blob, re.IGNORECASE | re.DOTALL):
            return True
    return False


def _find_partial_headers(lines: List[str], start_idx: int, max_lines: int = 3) -> Dict[str, List[int]]:
    """Trova parti di header distribuite su più righe."""
    found_parts = {}
    
    for label, parts in HEADER_PARTS.items():
        found_parts[label] = []
        for i in range(start_idx, min(start_idx + max_lines, len(lines))):
            line = lines[i]
            for part in parts:
                if re.search(r"\b" + re.escape(part) + r"\b", line, re.IGNORECASE):
                    if i not in found_parts[label]:
                        found_parts[label].append(i)
    
    return found_parts


def _detect_document_header(lines: List[str]) -> Dict[str, Any]:
    """Individua l'header della tabella DOCUMENTO gestendo headers multi-riga."""
    # Cerca prima "Tipologia documento", poi "Art. 73" come punto di partenza alternativo
    tipologia_idx = next((i for i, ln in enumerate(lines) if re.search(r"Tipologia\s+documento", ln, re.IGNORECASE)), None)
    art73_idx = next((i for i, ln in enumerate(lines) if re.search(r"^Art\.?\s*73\s*$", ln.strip(), re.IGNORECASE)), None)
    
    # Usa Art. 73 come punto di partenza se Tipologia documento non porta ai dati
    start_idx = tipologia_idx
    if art73_idx is not None and (tipologia_idx is None or art73_idx > tipologia_idx):
        start_idx = art73_idx
        
    result = {
        "start_index": None,
        "end_index": None,
        "header_lines": [],
        "header_blob": "",
        "found_labels": {lbl: False for lbl in HEADER_LABELS},
        "missing_labels": HEADER_LABELS.copy(),
        "partial_headers": {},
        "detection_strategy": "tipologia" if start_idx == tipologia_idx else "art73",
    }
    
    if start_idx is None:
        return result
    
    # Cerca parti di header distribuite su più righe partendo dal punto di inizio identificato
    max_search_lines = 12 if result["detection_strategy"] == "art73" else 8
    partial_headers = _find_partial_headers(lines, start_idx, max_lines=max_search_lines)
    result["partial_headers"] = partial_headers
    
    header_blob = lines[start_idx]
    end_idx = start_idx
    
    # Espande l'header - più righe se partiamo da Art. 73
    max_iterations = 8 if result["detection_strategy"] == "art73" else 3
    for iteration in range(max_iterations):
        # Aggiorna detection per il blob corrente
        for lbl in HEADER_LABELS:
            if not result["found_labels"][lbl]:  # Solo se non già trovato
                if _label_found(header_blob, lbl):
                    result["found_labels"][lbl] = True
                else:
                    # Verifica usando parti parziali per headers multi-riga
                    if lbl in partial_headers and len(partial_headers[lbl]) >= 2:
                        # Se abbiamo trovato almeno 2 parti dell'header su righe diverse, consideralo trovato
                        parts = HEADER_PARTS.get(lbl, [])
                        if len(parts) >= 2:
                            found_count = 0
                            for part in parts:
                                if any(re.search(r"\b" + re.escape(part) + r"\b", lines[idx], re.IGNORECASE) 
                                      for idx in partial_headers[lbl]):
                                    found_count += 1
                            if found_count >= 2:  # Trovate almeno 2 parti
                                result["found_labels"][lbl] = True
        
        # Se tutte le etichette sono state trovate, fermati
        if all(result["found_labels"].values()):
            break
            
        # Altrimenti prova ad aggiungere una riga
        if end_idx + 1 < len(lines):
            next_line = lines[end_idx + 1].strip()
            
            # NON aggiungere se la riga sembra essere dati invece che header
            is_data_line = False
            if next_line:
                # Righe che sembrano essere dati documento
                if (re.match(r"^\d+$", next_line) or  # Solo numeri
                    re.match(r"^\d{2}-\d{2}-\d{4}$", next_line) or  # Date
                    re.match(r"^[A-Z0-9]{6,7}$", next_line) or  # Codici destinatario
                    re.match(r"^[A-Z]{2,4}\s+\d+/\d+$", next_line) or  # Pattern FPR 123/45
                    re.match(r"^TD\d{2}\s+", next_line, re.IGNORECASE)):  # Tipologie TD (già elaborate)
                    is_data_line = True
            
            if not is_data_line:
                # Aggiungi solo se la riga sembra contenere parti di header
                contains_header_parts = False
                for parts in HEADER_PARTS.values():
                    for part in parts:
                        if re.search(r"\b" + re.escape(part) + r"\b", next_line, re.IGNORECASE):
                            contains_header_parts = True
                            break
                    if contains_header_parts:
                        break
                
                # Più conservativo per evitare di includere dati
                min_lines = 4 if result["detection_strategy"] == "art73" else 2
                if contains_header_parts or (iteration < min_lines and not is_data_line):
                    header_blob = header_blob + " " + next_line
                    end_idx += 1
                else:
                    break
            else:
                # È una riga di dati, ferma l'espansione dell'header
                break
        else:
            break
    
    # Calcola risultato finale
    result["start_index"] = start_idx
    result["end_index"] = end_idx
    result["header_lines"] = lines[start_idx:end_idx+1]
    result["header_blob"] = _norm_ws(header_blob)
    result["missing_labels"] = [k for k, v in result["found_labels"].items() if not v]
    
    return result


def _collect_document_row(lines: List[str], header_end: int) -> Tuple[str | None, List[str]]:
    """Raccoglie righe dati documento, gestendo header+dati sulla stessa riga e layout colonnari."""
    stops = re.compile(r"^(Cod\.|Prezzo totale|RIEPILOGHI|Totale documento)", re.IGNORECASE)
    buf: List[str] = []
    
    # Verifica se l'ultima riga dell'header contiene anche i dati
    if header_end < len(lines):
        header_line = lines[header_end]
        # Cerca pattern tipici di dati documento nell'ultima riga dell'header
        if re.search(r"\bTD\d{2}\b", header_line, re.IGNORECASE) or \
           re.search(r"\d{4}-\d{2}-\d{2}|\d{2}-\d{2}-\d{4}|\d{2}/\d{2}/\d{4}", header_line):
            # L'header contiene anche i dati, usa questa riga
            buf.append(header_line)
    
    # Aggiungi righe successive se non abbiamo già trovato dati nell'header
    if not buf:
        i = header_end + 1
        collected_data_lines = []
        
        # Cerca dati saltando righe vuote e raccogliendo righe con contenuto
        while i < len(lines) and len(collected_data_lines) < 10:  # Espande la ricerca
            ln = lines[i].strip()
            
            # Stop se troviamo sezioni successive
            if ln and stops.search(ln):
                break
                
            # Raccoglie righe non vuote che potrebbero contenere dati (INCLUDE tipologie TD!)
            if ln:
                # INCLUDE righe che iniziano con TDxx (contengono tipologie documento!)
                if re.match(r"^\s*TD\d{2}\b", ln, re.IGNORECASE):
                    collected_data_lines.append(ln)
                    buf.append(ln)
                    print(f"📄 Collected TD line [{i}]: '{ln}'")
                    i += 1
                    continue
                
                # Verifica se sembra contenere dati documento
                if (re.search(r"^\d+$", ln) or  # Solo numeri (numero documento)
                    re.search(r"\d{2}-\d{2}-\d{4}|\d{4}-\d{2}-\d{2}|\d{2}/\d{2}/\d{4}", ln) or  # Date
                    re.search(r"^[A-Z0-9]{6,7}$", ln) or  # Codice destinatario
                    re.search(r"^[A-Z]{2,4}\s+\d+/\d+$", ln) or  # Numeri con prefisso tipo "FPR 538/25"
                    re.search(r"^\d{4,}$", ln)):  # Numeri lunghi
                    collected_data_lines.append(ln)
                    buf.append(ln)
                    print(f"📄 Collected data line [{i}]: '{ln}'")
                # Per layout colonnari, aggiungi anche righe brevi senza lettere minuscole (evita descrizioni)
                elif (len(ln) < 30 and 
                      not re.search(r"[a-z]", ln) and  # Evita descrizioni in minuscolo
                      not re.search(r"\bfattura\b|\bnota\b|\bparcella\b", ln, re.IGNORECASE) and  # Evita termini tipologia
                      re.search(r"[0-9]", ln)):  # Deve contenere almeno un numero
                    collected_data_lines.append(ln)
                    buf.append(ln)
                    print(f"📄 Collected short line [{i}]: '{ln}'")
            i += 1
    
    text = _norm_ws(" ".join(buf)) if buf else None
    return (text, buf)


# ================================
# Parser principale (OCR)
# ================================

def parse_invoice_text(text: str) -> Dict[str, Any]:
    clean_text = "\n".join(_norm_ws(ln) for ln in text.replace("\r", "").splitlines())
    lines = [ln for ln in clean_text.split("\n")]

    data: Dict[str, Any] = {}
    

    # --------- Cedente/Prestatore ---------
    seller_m = re.search(r"Cedente/prestatore\s*\(fornitore\)(.*?)(Cessionario/committente|Tipologia documento)",
                         clean_text, re.IGNORECASE | re.DOTALL)
    if seller_m:
        sb = seller_m.group(1)
        denom = _extract_group(r"Denominazione\s*[:\-]?\s*(.*?)(?:Comune|Regime fiscale|Indirizzo|Cap|Provincia|Nazione|Telefono|$)", sb)
        if not denom or len(denom) < 5:
            m = re.search(r"Denominazione\s*[:\-]?\s*", sb, re.IGNORECASE)
            if m:
                tail = sb[m.end():]
                stop_re = re.compile(r"\b(Regime fiscale|Indirizzo|Comune|Provincia|Cap|Nazione|Telefono)\b", re.IGNORECASE)
                ms = stop_re.search(tail)
                if ms:
                    tail = tail[: ms.start()]
                denom = _norm_ws(tail) or None
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

    # --------- Cessionario/Committente ---------
    client_m = re.search(r"Cessionario/committente\s*\(cliente\)(.*?)(Tipologia documento|RIEPILOGHI|Cod\.)",
                         clean_text, re.IGNORECASE | re.DOTALL)
    if client_m:
        cb = client_m.group(1)
        c_denom = _extract_group(r"Denominazione\s*[:\-]?\s*(.*?)(?:Indirizzo|Comune|Provincia|Cap|Nazione|$)", cb)
        if not c_denom or len(c_denom) < 3:
            m = re.search(r"Denominazione\s*[:\-]?\s*", cb, re.IGNORECASE)
            if m:
                tail = cb[m.end():]
                stop_re = re.compile(r"\b(Indirizzo|Comune|Provincia|Cap|Nazione)\b", re.IGNORECASE)
                ms = stop_re.search(tail)
                if ms:
                    tail = tail[: ms.start()]
                c_denom = _norm_ws(tail) or None
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

    # --------- Header Documento (migliorato con correzione separazione header/valori) ---------
    header_dbg = _detect_document_header(lines)
    documento: Dict[str, Any] = {"tipo": None, "numero": None, "data": None, "codice_destinatario": None, "art_73": None}
    header_dbg["documento_initial"] = str(documento.copy())
    print(f"🟢 Header detection completed, strategy: {header_dbg.get('detection_strategy')}")
    print(f"📋 Header end at line {header_dbg.get('end_index')}, showing context:")
    
    # Mostra le righe intorno all'header per debug
    if header_dbg.get("end_index") is not None:
        end_idx = int(header_dbg["end_index"])
        start_context = max(0, end_idx - 2)
        end_context = min(len(lines), end_idx + 5)
        for i in range(start_context, end_context):
            marker = " --> " if i == end_idx else "     "
            print(f"📋 {marker}[{i:2d}]: {repr(lines[i])}")
    
    doc_row_text: str | None = None
    doc_row_lines: List[str] = []

    if header_dbg.get("end_index") is not None:
        doc_row_text, doc_row_lines = _collect_document_row(lines, int(header_dbg["end_index"]))
        print(f"📄 _collect_document_row result: text='{doc_row_text}', lines={doc_row_lines}")

    # --------- Parsing riga dati del documento (con correzione separazione header multi-riga) ---------
    if doc_row_text:
        # Crea pattern di pulizia più robusti per headers multi-riga
        header_clean_patterns = [
            r"\bArt\.?\s*73\b",
            r"\bTipologia\s+documento\b",
            r"\bNumero\s+documento\b",
            r"\bData\s+documento\b", 
            r"\bCodice\s+destinatario\b",
            r"\bCod\.\s+destinatario\b",
            # Pattern semplificati per parti isolate
            r"\bNumero\b(?=\s)",     # "Numero" isolato
            r"\bData\b(?=\s)",       # "Data" isolato  
            r"\bCodice\b(?=\s)",     # "Codice" isolato
            r"\bCod\.\b(?=\s)",      # "Cod." isolato
            r"\bdocumento\b",        # "documento" ovunque
            r"\bdestinatario\b",     # "destinatario" ovunque
        ]
        
        doc_row_clean = doc_row_text
        for pattern in header_clean_patterns:
            doc_row_clean = re.sub(pattern, " ", doc_row_clean, flags=re.IGNORECASE)
        
        # Pulizia aggiuntiva per spazi multipli e inizio riga
        doc_row_clean = re.sub(r"\s+", " ", doc_row_clean).strip()
        
        # Usa il testo pulito per il parsing
        tokens = re.findall(r"\S+", doc_row_clean)
        
        # Data
        mdate = DATE_RE.search(doc_row_clean)
        if mdate:
            documento["data"] = mdate.group(1)

        # Codice Destinatario
        cod_dest = None
        if documento["data"]:
            after = doc_row_clean.split(documento["data"], 1)[1]
            mcd = re.search(r"\b([A-Z0-9]{6,7})\b", after)
            if mcd:
                cod_dest = mcd.group(1)
        if not cod_dest:
            mcd2 = re.search(r"Cod(?:ice)?\.?\s*destinatario\s*[:\-]?\s*([A-Z0-9]{6,7})", doc_row_clean, re.IGNORECASE)
            cod_dest = mcd2.group(1) if mcd2 else None
        if cod_dest:
            documento["codice_destinatario"] = cod_dest

        # Numero Documento - per layout colonnare, cerca il primo token numerico che non è data o codice
        numero = None
        
        # Per layout colonnare (strategy = "art73"), usa approccio semplificato
        if header_dbg.get("detection_strategy") == "art73":
            # Prima cerca pattern multi-token come "FPR 538/25"
            doc_text = doc_row_clean
            
            # Cerca pattern prefisso + numero/anno 
            multi_token_match = re.search(r"\b([A-Z]{2,4})\s+(\d+/\d+)\b", doc_text)
            if multi_token_match:
                numero = f"{multi_token_match.group(1)} {multi_token_match.group(2)}"
            else:
                # Fallback: cerca token singoli
                for tok in tokens:
                    tok_clean = _cleanup_tok(tok)
                    if (tok_clean and 
                        not _looks_like_cod_dest(tok_clean) and 
                        not _is_law_token(tok_clean) and
                        tok_clean != documento.get("data") and
                        re.search(r"\d", tok_clean) and
                        not re.match(r"^\d{2}-\d{2}-\d{4}$", tok_clean)):  # Esclude date
                        numero = tok_clean
                        break
        else:
            # Logica originale per layout inline (strategia tipologia)
            print("⚡ Using tipologia strategy for numero extraction")
            if documento["data"]:
                try:
                    di = tokens.index(documento["data"])
                except ValueError:
                    di = None
                if di is not None:
                    # backward
                    i = di - 1
                    while i >= 0 and di - i <= 8:
                        tok = _cleanup_tok(tokens[i])
                        if tok and not _is_law_token(tok):
                            if (re.fullmatch(r"\d{8,}", tok) or
                                re.fullmatch(r"[A-Za-z0-9]{1,5}-\d{3,}", tok) or
                                ("/" in tok and not _is_law_token(tok) and re.search(r"\d", tok))):
                                pref = _cleanup_tok(tokens[i-1]) if i-1 >= 0 else ""
                                numero = f"{pref} {tok}" if re.fullmatch(r"[A-Za-z0-9]{1,5}-", pref) else tok
                                break
                        i -= 1
                    # forward
                    if not numero:
                        cands = []
                        for t in tokens[di + 1 : di + 8]:
                            t2 = _cleanup_tok(t)
                            if not t2 or _looks_like_cod_dest(t2) or _is_law_token(t2):
                                continue
                            if re.search(r"\d", t2):
                                cands.append(t2)
                        if cands:
                            numero = max(cands, key=_score_docnum)
            # label-based
            if not numero:
                m1 = re.search(r"Numero\s*documento\s*[:\-]?\s*([^\n\r]+)", doc_row_clean, re.IGNORECASE)
                if not m1:
                    m1 = re.search(r"N\.?\s*documento\s*[:\-]?\s*([^\n\r]+)", doc_row_clean, re.IGNORECASE)
                if m1:
                    cands = re.findall(r"[A-Za-z0-9/\-]+", m1.group(1))
                    cands = [t for t in cands if not _looks_like_cod_dest(t) and not _is_law_token(t)]
                    if cands:
                        numero = max(cands, key=_score_docnum)
        
        documento["numero"] = numero

        # Tipologia - se strategy = "art73", cerca nella sezione Tipologia documento separata
        tipo = None
        header_dbg["documento_before_tipologia"] = str(documento.copy())
        header_dbg["tipologia_initial_strategy"] = header_dbg.get("detection_strategy")
        header_dbg["tipologia_flow_started"] = True
        
        if header_dbg.get("detection_strategy") == "art73":
            header_dbg["tipologia_flow_path"] = "art73_branch"
            # Cerca la tipologia nella sezione "Tipologia documento" separata
            tipologia_match = re.search(r"Tipologia documento\s*\n\s*(.*?)(?:\n\s*Causale|\n\s*Cessionario|$)", 
                                       clean_text, re.IGNORECASE | re.DOTALL)
            if tipologia_match:
                tipo_section = tipologia_match.group(1).strip()
                tipo_raw = _norm_ws(tipo_section) or None
                
                # DEBUG: salva la sezione tipologia grezza
                header_dbg["tipologia_section_raw"] = tipo_raw or "NONE"
                
                # Separa rigorosamente tipologia da altri dati usando pattern TDxx
                if tipo_raw:
                    tipologie_note = _read_tipologie_known()
                    best_match = None
                    best_score = 0
                    
                    # Prima cerca match esatto del codice TD nel testo
                    td_match = re.search(r"\b(TD\d{2})\b", tipo_raw, re.IGNORECASE)
                    if td_match:
                        td_code = td_match.group(1).upper()
                        # DEBUG: salva il TD trovato
                        header_dbg["tipologia_td_found"] = td_code
                        
                        # Cerca pattern rigoroso: TD + descrizione fino al primo numero/data
                        # Estrae solo la parte tipologia, escludendo numeri e date
                        td_pattern = rf"\b{re.escape(td_code)}\b([^0-9]*?)(?:\s+\d+|\s+\d{{2}}-\d{{2}}-\d{{4}}|\s+[A-Z0-9]{{6,7}}|$)"
                        td_section_match = re.search(td_pattern, tipo_raw, re.IGNORECASE)
                        if td_section_match:
                            td_description = td_section_match.group(1).strip()
                            td_full = f"{td_code} {td_description}".strip()
                        else:
                            # Fallback: prende solo fino al primo spazio seguito da numero
                            td_parts = re.split(r'\s+(?=\d)', tipo_raw, 1)
                            td_full = td_parts[0].strip()
                        
                        # Match rigoroso con termini predefiniti
                        for cand in tipologie_note:
                            # Match esatto del codice TD
                            if cand.upper().startswith(td_code):
                                # Verifica similarità del resto del testo
                                cand_desc = cand[4:].strip()  # Rimuove "TDxx "
                                extracted_desc = td_full[4:].strip() if len(td_full) > 4 else ""
                                
                                if not extracted_desc:  # Solo codice TD
                                    best_match = cand
                                    best_score = 0.8
                                else:
                                    # Calcola similarità della descrizione
                                    similarity = difflib.SequenceMatcher(None, 
                                                                       extracted_desc.lower(), 
                                                                       cand_desc.lower()).ratio()
                                    if similarity > best_score:
                                        best_match = cand
                                        best_score = similarity
                        
                        # Usa il match se sufficientemente buono, altrimenti usa il TD estratto
                        if best_match and best_score >= 0.6:
                            tipo = best_match
                        else:
                            tipo = td_full
                        
                        # DEBUG: salva il risultato finale
                        header_dbg["tipologia_final"] = tipo
                    else:
                        # Nessun codice TD trovato, usa fuzzy matching generale
                        header_dbg["tipologia_td_found"] = "NO_TD_FOUND"
                        matches = difflib.get_close_matches(tipo_raw.lower(), 
                                                          [t.lower() for t in tipologie_note], 
                                                          n=1, cutoff=0.7)
                        if matches:
                            match_lower = matches[0]
                            for cand in tipologie_note:
                                if cand.lower() == match_lower:
                                    tipo = cand
                                    break
                        else:
                            tipo = tipo_raw
                        
                        # DEBUG: salva il risultato finale
                        header_dbg["tipologia_final"] = tipo
                else:
                    tipo = tipo_raw
        else:
            # APPROCCIO ROBUSTO: usa data e codici TD come ancore (strategia tipologia)
            print(f"🟠 Using robust TD+date approach, strategy: {header_dbg.get('detection_strategy')}")
            header_dbg["tipologia_flow_path"] = "robust_td_date_approach"
            
            if tokens and documento["data"]:
                print(f"🟤 Tokens: {tokens}")
                print(f"🔶 Data anchor: '{documento['data']}'")
                
                # Trova l'indice della data (ancora sicura)
                date_idx = None
                if documento["data"]:
                    try:
                        date_idx = tokens.index(documento["data"])
                    except ValueError:
                        # Prova formati alternativi
                        for i, token in enumerate(tokens):
                            if DATE_RE.match(token):
                                token_norm = token.replace("-", "/")
                                data_norm = documento["data"].replace("-", "/")
                                if token_norm == data_norm:
                                    date_idx = i
                                    break
                
                if date_idx is not None:
                    print(f"🔷 Date found at index {date_idx}")
                    
                    # Trova il primo codice TD nei token prima della data
                    tipologie_note = _read_tipologie_known()
                    tipo_found = None
                    td_start_idx = None
                    
                    # Cerca il codice TD più lungo che matcha
                    remaining_tokens = tokens[:date_idx]  # Tutti i token prima della data
                    remaining_text = " ".join(remaining_tokens)
                    print(f"🔍 Searching TD match in: '{remaining_text}'")
                    
                    for td_full in tipologie_note:
                        td_code = td_full[:4]  # Es: "TD24"
                        
                        # METODO 1: Cerca il codice TD esplicito nei token
                        td_explicit_found = False
                        for i in range(date_idx):
                            if tokens[i].upper().startswith(td_code):
                                # Match fuzzy con la tipologia completa
                                similarity = difflib.SequenceMatcher(None, 
                                                                   remaining_text.lower(), 
                                                                   td_full.lower()).ratio()
                                
                                if similarity > 0.5:  # Soglia di similarità
                                    if not tipo_found or similarity > tipo_found[1]:
                                        tipo_found = (td_full, similarity, i)
                                        td_start_idx = i
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
                                
                                print(f"🔎 Checking '{td_code}' significant part '{td_significant}' vs '{remaining_text}' → similarity: {similarity:.3f}")
                                
                                if similarity > 0.7:  # Soglia più alta per match parziali
                                    if not tipo_found or similarity > tipo_found[1]:
                                        tipo_found = (td_full, similarity, 0)
                                        td_start_idx = 0
                    
                    if tipo_found:
                        tipo = tipo_found[0]  # Usa la tipologia completa dai TD noti
                        print(f"🎯 Found TD match: '{tipo}' (similarity: {tipo_found[1]:.2f})")
                        
                        # STRATEGIA MIGLIORATA: Il numero documento è immediatamente prima della data
                        # Cerca nell'intero testo il pattern: [qualsiasi_cosa] [NUMERO] [DATA]
                        numero = None
                        
                        # Metodo 1: Trova il token immediatamente prima della data
                        if date_idx > 0:
                            potential_numero = tokens[date_idx - 1]
                            # Verifica che non sia parte della tipologia (evita DPR, 633/72, ecc.)
                            if (not re.search(r"^(DPR|lett\.|a\)|b\)|c\))$", potential_numero, re.IGNORECASE) and
                                not re.search(r"^\d{3}/\d{2}$", potential_numero)):  # Non DPR 633/72
                                numero = potential_numero
                                print(f"🔢 Method 1 - Token before date: '{numero}'")
                        
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
                                        print(f"🔢 Method 2 - Pattern match: '{numero}'")
                                        break
                        
                        if numero:
                            documento["numero"] = numero
                        else:
                            print("⚠️ Could not extract numero documento")
                    else:
                        # Fallback: prende tutto prima della data come tipologia grezza
                        # ANCHE qui estrai il numero documento prima della data
                        if date_idx > 0:
                            potential_numero = tokens[date_idx - 1]
                            if (not re.search(r"^(DPR|lett\.|a\)|b\)|c\))$", potential_numero, re.IGNORECASE) and
                                not re.search(r"^\d{3}/\d{2}$", potential_numero)):
                                numero = potential_numero
                                documento["numero"] = numero
                                print(f"🔢 Fallback - extracted numero: '{numero}'")
                                tipo_tokens = tokens[:date_idx-1]  # Esclude anche il numero
                            else:
                                tipo_tokens = tokens[:date_idx]  # Include tutto
                        else:
                            tipo_tokens = tokens[:date_idx]
                            
                        tipo = " ".join(tipo_tokens).strip()
                        print(f"⚠️  No TD match found, using raw text: '{tipo}'")
                else:
                    print("🔸 No date found in tokens")
        
        # DEBUG: salva il tipo prima della pulizia finale
        header_dbg["tipo_before_cleanup"] = repr(tipo)
        
        # Pulizia finale del tipo rimuovendo eventuali residui dell'header
        if tipo:
            tipo = re.sub(r"\b(Art\.?\s*73|Numero documento|Data documento|Cod(?:ice)?\.?\s*destinatario)\b", "", tipo, flags=re.IGNORECASE)
            tipo = _norm_ws(tipo)
        
        # DEBUG: salva il tipo finale
        header_dbg["tipo_after_cleanup"] = repr(tipo)
        print(f"🔴 Final assignment: tipo={repr(tipo)}")
        documento["tipo"] = tipo or None
        print(f"🔵 Final documento after tipo assignment: {documento}")

        # Art. 73: segnalazione presenza via header
        if any(re.search(r"Art\.?\s*73", ln, re.IGNORECASE) for ln in header_dbg.get("header_lines", [])):
            documento["art_73"] = "Art. 73"

        data["documento"] = documento
        print(f"🟣 Added documento to data: {data.get('documento')}")

    # --------- Righe Dettaglio ---------
    data["righe_dettaglio"] = []
    rows_block = re.search(r"Prezzo totale\n(.*?)RIEPILOGHI IVA E TOTALI", clean_text, re.DOTALL | re.IGNORECASE)
    if rows_block:
        pattern = re.compile(
            r"^(?P<desc>.*?)\s+"
            r"(?P<qta>\d{1,3}(?:[\.,]\d{1,3})?)\s+"
            r"(?P<pu>[\d\.,]+)\s+"
            r"(?P<um>[A-Z]{1,3})\s+"
            r"(?P<iva>[\d\.,]+)\s+"
            r"(?P<tot>[\d\.,]+)\s*$",
            re.MULTILINE
        )
        for m in pattern.finditer(rows_block.group(1)):
            g = m.groupdict()
            data["righe_dettaglio"].append({
                "descrizione": g["desc"].strip(),
                "quantita": _to_float(g["qta"]),
                "prezzo_unitario": _to_float(g["pu"]),
                "unita_misura": g["um"].strip(),
                "iva_percentuale": _to_float(g["iva"]),
                "prezzo_totale": _to_float(g["tot"]),
            })

    # --------- Riepilogo importi ---------
    data["riepilogo_importi"] = {
        "imponibile": _to_float(_extract_group(r"Totale imponibile\s+([\d\.,]+)", clean_text)),
        "imposta": _to_float(_extract_group(r"Totale imposta\s+([\d\.,]+)", clean_text)),
        "totale": _to_float(_extract_group(r"Totale documento\s+([\d\.,]+)", clean_text)),
    }

    # --------- Pagamento ---------
    pm = re.search(r"Data scadenza\s+([\d\-/]+)\s+([\d\.,]+)", clean_text)
    data["pagamento"] = {
        "modalita": _extract_group(r"\bMP\d{2}\s+(\w+)", clean_text),
        "scadenza": pm.group(1) if pm else None,
        "importo": _to_float(pm.group(2)) if pm else None,
    }

    # --------- DEBUG HEADER ---------
    data["debug_header"] = {
        "detected": bool(header_dbg.get("header_blob")),
        "header_start": header_dbg.get("start_index"),
        "header_end": header_dbg.get("end_index"),
        "header_lines": header_dbg.get("header_lines"),
        "header_blob": header_dbg.get("header_blob"),
        "found_labels": header_dbg.get("found_labels"),
        "missing_labels": header_dbg.get("missing_labels"),
        "partial_headers": header_dbg.get("partial_headers", {}),
        "detection_strategy": header_dbg.get("detection_strategy"),
        "doc_row_lines": doc_row_lines,
        "doc_row_text": doc_row_text,
        "doc_row_cleaned": doc_row_clean if 'doc_row_clean' in locals() else None,
    }

    return data


# =============================
# Utilities per I/O testo PDF + CSV
# =============================

class ExtractResult:
    def __init__(self, text: str, parsed: Dict[str, Any], ocr_used: bool):
        self.text = text
        self.parsed = parsed
        self.ocr_used = ocr_used


def _extract_text_pdf_native(pdf_path: str) -> str:
    """Estrae testo da PDF nativo. Ritorna stringa vuota se non riesce."""
    # pdfminer (preferito)
    try:
        from pdfminer.high_level import extract_text as pdfminer_extract_text  # type: ignore
        txt = pdfminer_extract_text(pdf_path) or ""
        if txt and len(txt.strip()) >= 10:
            return txt
    except Exception:
        pass
    # PyPDF2 fallback
    try:
        import PyPDF2  # type: ignore
        text = ""
        with open(pdf_path, "rb") as f:
            reader = PyPDF2.PdfReader(f)
            for pg in getattr(reader, "pages", []):
                try:
                    text += pg.extract_text() or ""
                except Exception:
                    continue
        return text
    except Exception:
        return ""


def _extract_text_pdf_ocr(pdf_path: str, lang: str = "ita+eng") -> str:
    """OCR via pdf2image+pytesseract. Ritorna stringa vuota se non disponibili."""
    try:
        from pdf2image import convert_from_path  # type: ignore
        import pytesseract  # type: ignore
    except Exception:
        return ""
    try:
        images = convert_from_path(pdf_path, dpi=300)
    except Exception:
        return ""
    chunks: List[str] = []
    for im in images:
        try:
            chunks.append(pytesseract.image_to_string(im, lang=lang))
        except Exception:
            continue
    return "\n".join(chunks)


def extract_invoice(pdf_path: str) -> ExtractResult:
    """Estrae il testo (nativo) e se serve fa OCR. Applica parse_invoice_text."""
    txt = _extract_text_pdf_native(pdf_path)
    parsed = parse_invoice_text(txt) if txt else {}
    ocr_used = False
    doc = (parsed or {}).get("documento", {}) if isinstance(parsed, dict) else {}
    needs_ocr = (not txt) or (not parsed) or (not doc) or (
        # Se non abbiamo numero e data e codice, prova OCR
        (not doc.get("numero") and not doc.get("data") and not doc.get("codice_destinatario"))
    )
    if needs_ocr:
        ocr_txt = _extract_text_pdf_ocr(pdf_path)
        if ocr_txt:
            ocr_used = True
            parsed = parse_invoice_text(ocr_txt)
            txt = ocr_txt
    return ExtractResult(txt, parsed or {}, ocr_used)


# Parser legacy per confronto (se presente): pdf_invoice.py
try:
    import pdf_invoice as legacy_pdf_utils  # type: ignore
except Exception:
    legacy_pdf_utils = None  # type: ignore


def _parse_legacy_text(text: str) -> Dict[str, Any] | None:
    if not text or legacy_pdf_utils is None:  # type: ignore
        return None
    try:
        return legacy_pdf_utils.parse_invoice_text(text)  # type: ignore
    except Exception:
        return None


def extract_invoice_legacy(pdf_path: str) -> Dict[str, Any] | None:
    txt = _extract_text_pdf_native(pdf_path)
    return _parse_legacy_text(txt)


def flatten_for_csv(parsed: Dict[str, Any], pdf_path: str, *, parser_name: str) -> Dict[str, str]:
    def g(*keys, default="") -> str:
        cur: Any = parsed
        for k in keys:
            if not isinstance(cur, dict):
                return default
            cur = cur.get(k)
            if cur is None:
                return default
        return str(cur)

    # includo colonne di debug per l'header
    return {
        "parser": parser_name,
        "file": pdf_path,
        "fornitore_denominazione": g("fornitore", "denominazione"),
        "fornitore_piva": g("fornitore", "p_iva"),
        "cliente_denominazione": g("cliente", "denominazione"),
        "cliente_piva": g("cliente", "p_iva"),
        "documento_tipologia": g("documento", "tipo"),
        "documento_numero": g("documento", "numero"),
        "documento_data": g("documento", "data"),
        "documento_codice_destinatario": g("documento", "codice_destinatario"),
        "totale_imponibile": g("riepilogo_importi", "imponibile"),
        "totale_imposta": g("riepilogo_importi", "imposta"),
        "totale_documento": g("riepilogo_importi", "totale"),
        "pagamento_modalita": g("pagamento", "modalita"),
        "pagamento_scadenza": g("pagamento", "scadenza"),
        "pagamento_importo": g("pagamento", "importo"),
        # Debug header detection esteso
        "debug_header_detected": g("debug_header", "detected"),
        "debug_header_start": g("debug_header", "header_start"),
        "debug_header_end": g("debug_header", "header_end"),
        "debug_header_lines": "|".join(parsed.get("debug_header", {}).get("header_lines", [])),
        "debug_found_labels": g("debug_header", "found_labels"),
        "debug_missing_labels": g("debug_header", "missing_labels"),
        "debug_partial_headers": g("debug_header", "partial_headers"),
        "debug_detection_strategy": g("debug_header", "detection_strategy"),
        "debug_doc_row_lines": "|".join(parsed.get("debug_header", {}).get("doc_row_lines", [])),
        "debug_doc_row_text": g("debug_header", "doc_row_text"),
        "debug_doc_row_cleaned": g("debug_header", "doc_row_cleaned"),
        # Debug tipologia processing
        "debug_tipologia_section_raw": g("debug_header", "tipologia_section_raw"),
        "debug_tipologia_td_found": g("debug_header", "tipologia_td_found"),
        "debug_tipologia_final": g("debug_header", "tipologia_final"),
        # Altri debug
        "debug_tokens_all": "|".join(parsed.get("debug_header", {}).get("all_tokens", [])),
        "debug_fallback_separation": str(parsed.get("debug_header", {}).get("fallback_separation", "")),
        "debug_tipologia_strategy_path": g("debug_header", "tipologia_strategy_path"),
        "debug_tipologia_strategy_debug": str(parsed.get("debug_header", {}).get("tipologia_strategy_debug", "")),
        "debug_tipologia_initial_strategy": g("debug_header", "tipologia_initial_strategy"),
        "debug_tipologia_flow_started": g("debug_header", "tipologia_flow_started"),
        "debug_tipologia_flow_path": g("debug_header", "tipologia_flow_path"),
        "debug_tipo_before_cleanup": g("debug_header", "tipo_before_cleanup"),
        "debug_tipo_after_cleanup": g("debug_header", "tipo_after_cleanup"),
        "debug_documento_initial": g("debug_header", "documento_initial"),
        "debug_documento_before_tipologia": g("debug_header", "documento_before_tipologia"),
        "debug_date_format_mismatch": g("debug_header", "date_format_mismatch"),
        "debug_date_pattern_match": g("debug_header", "date_pattern_match"),
        "debug_file_hash": f"{hash(pdf_path) % 10000:04d}",
    }


def write_csv(rows: List[Dict[str, str]], out_path: str, sep: str = ";") -> None:
    import csv
    if not rows:
        with open(out_path, "w", encoding="utf-8", newline="") as f:
            f.write("")
        return
    headers = list(rows[0].keys())
    with open(out_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=headers, delimiter=sep)
        writer.writeheader()
        for r in rows:
            writer.writerow(r)


# =============================
# CLI
# =============================
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="OCR/parse Fatture (NUOVO) → CSV con debug header")
    parser.add_argument("pdf", nargs="*", default=[
        r"C:/__Projects/__dev_Massimo/gmail/azienda.agricola/fatture/split/2025-08-05 Fattura V2- 250038010 PROGEO SCA.pdf",
        r"C:/__Projects/__dev_Massimo/gmail/azienda.agricola/fatture/split/2025-07-31 Fattura 633_72 8225089597 Eurocap Petroli SpA.pdf",
        r"C:/__Projects/__dev_Massimo/gmail/azienda.agricola/fatture/split/2025-07-21 Fattura 20788_2025_G1 DUSTY RENDERING S.R.L..pdf",
        r"C:/__Projects/__dev_Massimo/gmail/azienda.agricola/fatture/split/2025-07-22 Fattura 1191_2025 F.LLI RICCI SRL.pdf",
        r"C:/__Projects/__dev_Massimo/gmail/azienda.agricola/fatture/split/2025-07-23 Fattura 112505418437 HERA S.p.A..pdf",
        r"C:/__Projects/__dev_Massimo/gmail/azienda.agricola/fatture/split/2025-07-23 Fattura 112505493391 HERA S.p.A..pdf",
        r"C:/__Projects/__dev_Massimo/gmail/azienda.agricola/fatture/split/2025-07-23 Fattura None Bernardini Francesco.pdf",
        r"C:/__Projects/__dev_Massimo/gmail/azienda.agricola/fatture/split/2025-07-23 Fattura V2- 250035405 PROGEO SCA.pdf",
        r"C:/__Projects/__dev_Massimo/gmail/azienda.agricola/fatture/split/2025-07-24 Fattura V2- 250035610 PROGEO SCA.pdf",
        r"C:/__Projects/__dev_Massimo/gmail/azienda.agricola/fatture/split/2025-07-30 Fattura 005258882692 Enel Energia S.p.A..pdf",
        r"C:/__Projects/__dev_Massimo/gmail/azienda.agricola/fatture/split/2025-07-30 Fattura 190_2025 OFFICINA MARTENSI S.R.L.pdf",
        r"C:/__Projects/__dev_Massimo/gmail/azienda.agricola/fatture/split/2025-07-30 Fattura None RIVI PAOLO & C. SAS.pdf",
        r"C:/__Projects/__dev_Massimo/gmail/azienda.agricola/fatture/split/2025-07-30 Fattura V2- 250036527 PROGEO SCA.pdf",
        r"C:/__Projects/__dev_Massimo/gmail/azienda.agricola/fatture/split/2025-07-31 Fattura 00000002029 Oleodinamica Sassolese s.r.l. Unipersonale.pdf",
        r"C:/__Projects/__dev_Massimo/gmail/azienda.agricola/fatture/split/2025-07-31 Fattura 217_F2025 ELETTROMILK s.r.l. Mungitura-Zootecnia-.pdf",
        r"C:/__Projects/__dev_Massimo/gmail/azienda.agricola/fatture/split/2025-07-31 Fattura 2632_00 EMMEDIELLE S.R.L..pdf",
        r"C:/__Projects/__dev_Massimo/gmail/azienda.agricola/fatture/split/2025-07-31 Fattura 5503_2025 VETEMONTANA SRL.pdf",
        r"C:/__Projects/__dev_Massimo/gmail/azienda.agricola/fatture/split/2025-07-31 Fattura 559_M_25 ANTONELLI E IACCONI SRL.pdf",
        r"C:/__Projects/__dev_Massimo/gmail/azienda.agricola/fatture/split/2025-07-31 Fattura None COM-FER SRL.pdf",
        r"C:/__Projects/__dev_Massimo/gmail/azienda.agricola/fatture/split/2025-07-31 Fattura V2- 250036719 PROGEO SCA.pdf",
        r"C:/__Projects/__dev_Massimo/gmail/azienda.agricola/fatture/split/2025-08-06 Fattura 142500026594 HERACQUAMODENA S.R.L..pdf",
        r"C:/__Projects/__dev_Massimo/gmail/azienda.agricola/fatture/split/2025-08-07 Fattura V2- 250038403 PROGEO SCA.pdf",
    ], help="Percorsi PDF da processare")
    parser.add_argument("-o", "--out", default="./fatture_parsed_ocr.csv", help="Percorso CSV in uscita")
    parser.add_argument("--compare-native", action="store_true",
                        help="Aggiunge anche la riga del parser legacy (solo PDF testuali)")
    parser.add_argument("--debug-headers", action="store_true",
                        help="Stampa a video i dettagli dell'header DOCUMENTO rilevato")

    args = parser.parse_args()

    rows: List[Dict[str, str]] = []
    for pth in args.pdf:
        if not os.path.exists(pth):
            print("File non trovato:", pth)
            continue
        res = extract_invoice(pth)
        if args.debug_headers:
            dbg = res.parsed.get("debug_header", {})
            print("\n=== DEBUG HEADER per:", pth)
            print("detected:", dbg.get("detected"))
            print("header_start..end:", dbg.get("header_start"), dbg.get("header_end"))
            print("header_lines:", dbg.get("header_lines"))
            print("found_labels:", dbg.get("found_labels"))
            print("missing_labels:", dbg.get("missing_labels"))
            print("partial_headers:", dbg.get("partial_headers"))
            print("detection_strategy:", dbg.get("detection_strategy"))
            print("doc_row_lines:", dbg.get("doc_row_lines"))
            print("doc_row_text:", repr(dbg.get("doc_row_text")))
            print("doc_row_cleaned:", repr(dbg.get("doc_row_cleaned")))
        # AGGIUNTO: Output di debug per verificare i risultati
        doc = res.parsed.get('documento', {})
        print(f"\n=== RISULTATI PARSING per {pth.split('/')[-1] if '/' in pth else pth.split(chr(92))[-1]} ===")
        print(f"documento_tipo: {repr(doc.get('tipo'))}")
        print(f"documento_numero: {repr(doc.get('numero'))}")
        print(f"documento_data: {repr(doc.get('data'))}")
        print(f"documento_codice_destinatario: {repr(doc.get('codice_destinatario'))}")
        
        rows.append(flatten_for_csv(res.parsed, pth, parser_name="new_ocr"))

        # Confronto parser legacy (se disponibile)
        if args.compare_native and legacy_pdf_utils is not None:  # type: ignore
            legacy = extract_invoice_legacy(pth)
            if legacy:
                rows.append(flatten_for_csv(legacy, pth, parser_name="legacy"))

    write_csv(rows, args.out, sep=";")
    print(f"CSV scritto: {args.out} — righe: {len(rows)}")
    
    # Output finale in formato tabellare per verificare i risultati
    print(f"\n=== RIEPILOGO TOTALE - {len(rows)} FATTURE PROCESSATE ===")
    for i, row in enumerate(rows, 1):
        print(f"\nFATTURA #{i}: {row.get('file', 'N/A').split('/')[-1] if '/' in row.get('file', '') else row.get('file', 'N/A').split(chr(92))[-1]}")
        print(f"  Tipologia: {row.get('documento_tipologia', 'N/A')}")
        print(f"  Numero:    {row.get('documento_numero', 'N/A')}")
        print(f"  Data:      {row.get('documento_data', 'N/A')}")
        print(f"  Destinatario: {row.get('documento_codice_destinatario', 'N/A')}")
        
    print("\n=== FINE ELABORAZIONE ===")
