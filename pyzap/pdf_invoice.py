from __future__ import annotations

from typing import Any, Dict, Iterable, List, Tuple
import re
import os
import difflib

# DEBUG FLAG - Controlla tutti i messaggi di debug
DEBUG_ENABLED = False


def _norm_ws(s: str) -> str:
    """Normalizza gli spazi bianchi: rimuove \r, converte spazi multipli in singoli"""
    return re.sub(r"\s+", " ", s.replace("\r", " ").strip())


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


def _extract_text_pdf_native(pdf_path: str, debug: bool = False) -> str:
    """Estrae testo da PDF nativo. Usa pdfminer.six come preferito, PyPDF2 come fallback."""
    # pdfminer.six (preferito) - più robusto per la struttura del testo
    try:
        from pdfminer.high_level import extract_text as pdfminer_extract_text  # type: ignore
        txt = pdfminer_extract_text(pdf_path) or ""
        if txt and len(txt.strip()) >= 10:
            if debug:
                print(f"DEBUG Using pdfminer.six for extraction")
            return txt
    except Exception as e:
        if debug:
            print(f"DEBUG pdfminer failed: {e}")
        pass
    
    # PyPDF2 fallback (meno affidabile per struttura testo)
    try:
        import PyPDF2  # type: ignore
        if debug:
            print(f"DEBUG Using PyPDF2 fallback")
        text = ""
        with open(pdf_path, "rb") as f:
            reader = PyPDF2.PdfReader(f)
            for pg in getattr(reader, "pages", []):
                try:
                    text += pg.extract_text() or ""
                except Exception:
                    continue
        # Normalizza il testo PyPDF2 per separare le righe concatenate
        if text:
            text = _normalize_pypdf_text(text)
        return text
    except Exception as e:
        if debug:
            print(f"DEBUG PyPDF2 failed: {e}")
        return ""


def _extract_text_pdf_ocr(pdf_path: str, lang: str = "ita+eng", debug: bool = False) -> str:
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


class ExtractResult:
    """Risultato dell'estrazione PDF con metadati."""
    def __init__(self, text: str, parsed: Dict[str, Any], ocr_used: bool):
        self.text = text
        self.parsed = parsed
        self.ocr_used = ocr_used


def _normalize_pypdf_text(text: str) -> str:
    """Normalizza il testo estratto da PyPDF2 che concatena le righe senza spazi."""
    lines = text.replace("\r", "").splitlines()
    normalized_lines = []
    
    for line in lines:
        line = line.strip()
        if not line:
            normalized_lines.append("")
            continue
            
        # Separa righe concatenate tipiche
        # Pattern: "Telefono: XXXCessionario/committente" -> separa dopo il numero di telefono
        line = re.sub(r"(\d{10})([A-Z][a-z])", r"\1\n\2", line)
        
        # Pattern: "Tipologia documento Art. 73Numero" -> separa in parti logiche  
        line = re.sub(r"(Tipologia documento)\s+(Art\.\s*73)\s*([A-Z][a-z])", r"\1\n\2\n\3", line)
        
        # Pattern: "documento Data" -> separa quando vediamo "documento" seguito da maiuscola
        line = re.sub(r"(documento)\s+([A-Z][a-z])", r"\1\n\2", line)
        
        # Pattern: "destinatario " -> separa dopo destinatario
        line = re.sub(r"(destinatario)\s+([A-Z])", r"\1\n\2", line)
        
        # Pattern: "a) DPR 633/72 V2-" -> separa il numero documento
        line = re.sub(r"(DPR\s+\d+/\d+)\s+([A-Z0-9]+[-/_\\])", r"\1\n\2", line)
        
        # Pattern: "V2-250039161 12-08-2025" -> separa numero e data documento
        line = re.sub(r"([A-Z0-9]+[-/_\\]\d+)\s+(\d{2}-\d{2}-\d{4})", r"\1\n\2", line)
        
        # Aggiungi le righe risultanti (potrebbero essere multiple dopo la separazione)
        if "\n" in line:
            normalized_lines.extend(line.split("\n"))
        else:
            normalized_lines.append(line)
    
    return "\n".join(normalized_lines)


def extract_invoice_from_pdf(pdf_path: str, debug: bool = False) -> ExtractResult:
    """Estrae il testo (nativo) e se serve fa OCR. Applica parse_invoice_text."""
    if debug:
        print(f"DEBUG EXTRACT_INVOICE: Processing {pdf_path}")
    txt = _extract_text_pdf_native(pdf_path, debug)
    if debug:
        print(f"DEBUG NATIVE TEXT: {len(txt) if txt else 0} chars extracted")
    
    parsed = parse_invoice_text(txt, debug) if txt else {}
    ocr_used = False
    doc = (parsed or {}).get("documento", {}) if isinstance(parsed, dict) else {}
    needs_ocr = (not txt) or (not parsed) or (not doc) or (
        # Se non abbiamo numero e data e codice, prova OCR
        (not doc.get("numero") and not doc.get("data") and not doc.get("codice_destinatario"))
    )
    if debug:
        print(f"DEBUG NEEDS_OCR: {needs_ocr} (txt={bool(txt)}, parsed={bool(parsed)}, doc={bool(doc)})")
    if needs_ocr:
        if debug:
            print("DEBUG Starting OCR extraction...")
        ocr_txt = _extract_text_pdf_ocr(pdf_path, debug=debug)
        if debug:
            print(f"DEBUG OCR TEXT: {len(ocr_txt) if ocr_txt else 0} chars extracted")
        if ocr_txt:
            ocr_used = True
            parsed = parse_invoice_text(ocr_txt, debug)
            txt = ocr_txt
    return ExtractResult(txt, parsed or {}, ocr_used)


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


# Variabili globali per supportare la logica avanzata
LAW_TOKENS = {"633/72", "600/73", "600/1973"}
HEADER_LABELS = ["Tipologia documento", "Art. 73", "Numero documento", "Data documento", "Codice destinatario"]
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


def _is_law_token(tok: str) -> bool:
    if "/" in tok and re.fullmatch(r"\d{3}/\d{2}", tok):
        return True
    return tok in LAW_TOKENS or (tok.upper().startswith("DPR") and "633/72" in tok)


def _looks_like_cod_dest(tok: str) -> bool:
    return bool(re.fullmatch(r"[A-Z0-9]{6,7}", tok))


def _cleanup_tok(tok: str) -> str:
    tok = tok.strip().strip(".,;:()[]{}") 
    tok = re.sub(r"[^A-Za-z0-9/\-_\\]", "", tok)
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
    result["header_blob"] = _norm_ws(header_blob) if 'header_blob' in locals() else ""
    result["missing_labels"] = [k for k, v in result["found_labels"].items() if not v]
    
    return result


def _collect_document_row(lines: List[str], header_end: int, debug: bool = False) -> Tuple[str | None, List[str]]:
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
                if debug:
                    print(f"DEBUG Evaluating line [{i}]: '{ln}'")
                # INCLUDE righe che iniziano con TDxx (contengono tipologie documento!)
                if re.match(r"^\s*TD\d{2}\b", ln, re.IGNORECASE):
                    collected_data_lines.append(ln)
                    buf.append(ln)
                    if debug:
                        print(f"DEBUG Collected TD line [{i}]: '{ln}'")
                    i += 1
                    continue
                
                # Verifica se sembra contenere dati documento
                if (re.search(r"^\d+$", ln) or  # Solo numeri (numero documento)
                    re.search(r"\d{2}-\d{2}-\d{4}|\d{4}-\d{2}-\d{2}|\d{2}/\d{2}/\d{4}", ln) or  # Date
                    re.search(r"^[A-Z0-9]{6,7}$", ln) or  # Codice destinatario
                    re.search(r"^[A-Z]{2,4}\s+\d+/\d+$", ln) or  # Numeri con prefisso tipo "FPR 538/25"
                    re.search(r"^\d{4,}$", ln) or  # Numeri lunghi
                    re.search(r"DPR\s+\d+/\d+\s+V2-", ln)):  # Righe con V2- (importante!)
                    collected_data_lines.append(ln)
                    buf.append(ln)
                    if debug:
                        print(f"DEBUG Collected data line [{i}]: '{ln}'")
                # Per layout colonnari, aggiungi anche righe brevi senza lettere minuscole (evita descrizioni)
                elif (len(ln) < 30 and 
                      not re.search(r"[a-z]", ln) and  # Evita descrizioni in minuscolo
                      not re.search(r"\bfattura\b|\bnota\b|\bparcella\b", ln, re.IGNORECASE) and  # Evita termini tipologia
                      (re.search(r"[0-9]", ln) or re.search(r"[A-Z]{1,4}[-/_\\]", ln))):  # Deve contenere numeri O prefissi
                    collected_data_lines.append(ln)
                    buf.append(ln)
                    if debug:
                        print(f"DEBUG Collected short line [{i}]: '{ln}'")
            i += 1
    
    text = _norm_ws(" ".join(buf)) if buf else None
    return (text, buf)


def parse_invoice_text(text: str, debug: bool = False) -> Dict[str, Any]:
    """Extract fields from Italian electronic invoice OCR/text `text`.
    Mantiene la stessa interfaccia della versione originale.
    Migliorie:
      - Denominazione (fornitore/cliente) multiline -> robusto a line break OCR.
      - Numero documento -> ignora token di legge (es. 'DPR 633/72').
      - Gestione avanzata header multi-riga.
    """

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

    # Usa il testo direttamente se pdfminer funziona bene, altrimenti normalizza per PyPDF2
    clean_text = "\n".join(_norm_ws(ln) for ln in text.replace("\r", "").splitlines())
    lines = [ln for ln in clean_text.split("\n")]

    # DEBUG: mostra le prime 20 righe del testo estratto
    if debug:
        print(f"DEBUG TEXT EXTRACTION - Found {len(lines)} lines total")
        print("DEBUG First 20 lines:")
        for i, line in enumerate(lines[:20]):
            print(f"DEBUG [{i:2d}]: {repr(line)}")
        
        if len(lines) > 20:
            print("DEBUG ... (showing only first 20 lines)")

    data: Dict[str, Any] = {}
    DATE_RE = re.compile(r"\b(\d{4}-\d{2}-\d{2}|\d{2}-\d{2}-\d{4}|\d{2}/\d{2}/\d{4})\b")

    # --------- Cedente/Prestatore ---------
    seller_m = re.search(r"Cedente/prestatore\s*\(fornitore\)(.*?)(Cessionario/committente|Tipologia documento)",
                         clean_text, re.IGNORECASE | re.DOTALL)
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

    # --------- Cessionario/Committente ---------
    client_m = re.search(r"Cessionario/committente\s*\(cliente\)(.*?)(Tipologia documento|RIEPILOGHI|Cod\.)",
                         clean_text, re.IGNORECASE | re.DOTALL)
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

    # --------- Header Documento (migliorato con correzione separazione header/valori) ---------
    header_dbg = _detect_document_header(lines)
    documento: Dict[str, Any] = {"tipo": None, "numero": None, "data": None, "codice_destinatario": None, "art_73": None}
    header_dbg["documento_initial"] = str(documento.copy())
    if debug:
        print(f"DEBUG Header detection completed, strategy: {header_dbg.get('detection_strategy')}")
        print(f"DEBUG Header end at line {header_dbg.get('end_index')}, showing context:")
    
    # Mostra le righe intorno all'header per debug
    if header_dbg.get("end_index") is not None:
        end_idx = int(header_dbg["end_index"])
        start_context = max(0, end_idx - 2)
        end_context = min(len(lines), end_idx + 5)
        for i in range(start_context, end_context):
            marker = " --> " if i == end_idx else "     "
            if debug:
                print(f"DEBUG {marker}[{i:2d}]: {repr(lines[i])}")
    
    doc_row_text: str | None = None
    doc_row_lines: List[str] = []

    if header_dbg.get("end_index") is not None:
        doc_row_text, doc_row_lines = _collect_document_row(lines, int(header_dbg["end_index"]), debug)
        if debug:
            print(f"DEBUG _collect_document_row result: text='{doc_row_text}', lines={doc_row_lines}")

    # --------- Parsing riga dati del documento (con correzione separazione header multi-riga) ---------
    if doc_row_text and doc_row_lines:
        # Usa direttamente le righe raccolte da _collect_document_row 
        # invece di ri-processare il testo concatenato
        hz_clean = " ".join(doc_row_lines)
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

        # ESTRAZIONE NUMERO CON STRATEGIA MIGLIORATA (V2- prioritario + multi-riga + date-anchored)
        numero: str | None = None
        
        # PRIORITARIO: Cerca pattern V2- specifici nell'intero testo (gestisce newlines)
        v2_match = re.search(r'\bV2[\s\-_/\\]*(\d{6,})', hz_clean)
        if v2_match:
            numero = f"V2-{v2_match.group(1)}"
            if debug:
                print(f"DEBUG Found V2- pattern (priority): '{numero}'")
        
        # SECONDO: Se non V2-, controlla altri pattern multi-riga
        if not numero:
            if debug:
                print(f"DEBUG doc_row_lines: {doc_row_lines}")
                print(f"DEBUG Looking for numero in collected tokens...")
            
            # Cerca pattern numero documento nei token raccolti (esclusa tipologia e data)
            numero_candidates = []
            for i, line in enumerate(doc_row_lines):
                # Escludi la tipologia TD
                if re.match(r"^\s*TD\d{2}\b", line, re.IGNORECASE):
                    continue
                # Escludi le date
                if re.match(r"^\s*\d{2}-\d{2}-\d{4}$", line.strip()):
                    continue
                # Pattern per numeri documento: prefisso + numero o solo numero lungo
                if (re.match(r"^[A-Z0-9]{1,4}[-/_\\\\]?$", line.strip()) or  # Prefisso come "V2-", "ABC/", "FPR_", "XYZ\"
                    re.match(r"^\d{6,}$", line.strip()) or  # Numero lungo
                    re.match(r"^[A-Z0-9]{1,8}[-/_\\\\]+[A-Z0-9]+[-/_\\\\]*[A-Z0-9]*$", line.strip()) or  # Formato completo con separatori (es. 20788/2025/G1)
                    re.match(r"^[A-Z]{2,4}\s+\d{3,}[-/_\\\\]*[A-Z0-9]*$", line.strip()) or  # Formato con spazio (es. FPR 538/25)
                    re.match(r"^[A-Z]{1,3}\d{4,}$", line.strip())):  # Formato lettera+cifre (es. B002079)
                    numero_candidates.append(line.strip())
                    if debug:
                        print(f"DEBUG Found numero candidate [{i}]: '{line.strip()}'")
            
            if debug:
                print(f"DEBUG numero_candidates: {numero_candidates}")
            
            # Ricostruisci il numero documento dai candidates
            if len(numero_candidates) >= 2:
                # Se abbiamo prefisso + numero separati (tipo "V2-" + "250039161")
                prefix = numero_candidates[0]
                number = numero_candidates[1]
                if re.match(r"^[A-Z0-9]{1,4}[-/_\\\\]?$", prefix) and re.match(r"^\d{6,}$", number):
                    # Se il prefisso finisce con un separatore, non aggiungere spazio
                    if re.search(r"[-/_\\\\]$", prefix):
                        numero = f"{prefix}{number}"
                    else:
                        numero = f"{prefix} {number}"
                    if debug:
                        print(f"DEBUG Combined numero from prefix+number: '{numero}'")
            elif len(numero_candidates) == 1:
                # Numero già formato o solo prefisso - CONTROLLA se non è già coperto da V2
                candidate = numero_candidates[0]
                if not candidate.isdigit() or not v2_match:  # Evita duplicati V2
                    numero = candidate
                    if debug:
                        print(f"DEBUG Single numero candidate: '{numero}'")
            
            # TERZO: Cerca anche pattern FPR XXX/XX nel testo completo
            if not numero:
                fpr_match = re.search(r'\bFPR\s+\d+/\d+', hz_clean)
                if fpr_match:
                    numero = fpr_match.group(0)
                    if debug:
                        print(f"DEBUG Found FPR pattern: '{numero}'")
        
        # Se non trovato con metodo multi-riga, usa approccio date-anchored classico
        if not numero and date_idx is not None:
            if debug:
                print("DEBUG Using fallback date-anchored approach for numero")
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
                matches = re.findall(r'\b([A-Z]{1,4}[-/_\\]*\d+(?:[/_\\]\d+)?|\d+(?:[/_\\]\d+)?)\b', text_before_date)
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
            "art_73": "Art. 73" if re.search(r"Art\.?\s*73", clean_text, re.IGNORECASE) else None,
        }

    # ---------------- Righe dettaglio ----------------
    data["righe_dettaglio"] = []
    rows_block = re.search(r"Prezzo totale\n(.*?)RIEPILOGHI IVA E TOTALI", clean_text, re.DOTALL | re.IGNORECASE)
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
        "imponibile": _to_float(_extract_group(r"Totale imponibile\s+([\d\.,]+)", clean_text)),
        "imposta": _to_float(_extract_group(r"Totale imposta\s+([\d\.,]+)", clean_text)),
        "totale": _to_float(_extract_group(r"Totale documento\s+([\d\.,]+)", clean_text)),
    }

    # ---------------- Pagamento ----------------
    
    # MODALITA PAGAMENTO - gestione di entrambi i layout (PyPDF2 inline e PDFMiner multiline)
    modalita = None
    
    # Metodo 1: Layout inline (PyPDF2) - "MP12 RIBA Data scadenza"
    mp_inline = re.search(r"\bMP\d{2}\s+([A-Z][a-zA-Z]+)", clean_text)
    if mp_inline:
        candidate = mp_inline.group(1)
        # Verifica che non sia una parola generica come "Data", "Allegati", etc.
        if candidate not in ['Data', 'Allegati', 'IBAN', 'Sconto', 'ABI', 'Codice', 'CAB']:
            modalita = candidate
    
    # Metodo 2: Layout multiline (PDFMiner) - cerca modalità prima di MP##
    if not modalita:
        # Pattern specifico per PDFMiner: cerca modalità nell'area "Modalit� pagamento"
        mp_section = re.search(r'Modalit.\s*pagamento.*?MP\d{2}', clean_text, re.DOTALL | re.IGNORECASE)
        if mp_section:
            section_text = mp_section.group(0)
            # Cerca modalità di pagamento nota in questa sezione
            payment_types = ['RIBA', 'SEPA Direct Debit', 'SEPA', 'Bonifico', 'Domiciliazione', 'Contanti', 'RID', 'Assegno']
            for ptype in payment_types:
                if re.search(r'\b' + re.escape(ptype), section_text, re.IGNORECASE):
                    modalita = ptype
                    break
    
    # SCADENZA E IMPORTO - gestione di entrambi i layout
    scadenza = None
    importo = None
    
    # Metodo 1: Layout inline (PyPDF2) - "Data scadenza 10-09-2025 1.000,50"
    pm_inline = re.search(r"Data scadenza\s+([\d\-/]+)\s+([\d\.,]+)", clean_text)
    if pm_inline:
        scadenza = pm_inline.group(1)
        importo = _to_float(pm_inline.group(2))
    
    # Metodo 2: Layout multiline (PDFMiner) - scadenza e importo separati
    if not scadenza:
        # Cerca scadenza separatamente
        scadenza_match = re.search(r"Data scadenza\s+([\d\-/]+)", clean_text)
        if scadenza_match:
            scadenza = scadenza_match.group(1)
            
            # Cerca importo nella sezione pagamento dopo la scadenza
            # Strategia 1: Cerca nella sezione MP## estesa (include anche dopo Allegati)
            mp_section_extended = re.search(r'MP\d{2}.*?(?=\x0c|$)', clean_text, re.DOTALL | re.IGNORECASE)
            if mp_section_extended:
                section_text = mp_section_extended.group(0)
                # Cerca importi nella sezione (formato italiano con virgola)
                amounts = re.findall(r'(-?\d{1,3}(?:\.\d{3})*,\d{2})', section_text)
                if amounts:
                    # Prende l'ultimo importo nella sezione (più probabile sia quello di pagamento)
                    importo = _to_float(amounts[-1])
            
            # Strategia 2: Se non trovato, cerca importo vicino alla data scadenza
            if not importo:
                # Cerca nell'area intorno alla data scadenza
                scadenza_pos = clean_text.find(scadenza)
                if scadenza_pos >= 0:
                    # Estrai contesto dopo la scadenza (200 caratteri)
                    context_after = clean_text[scadenza_pos:scadenza_pos + 200]
                    amounts_near = re.findall(r'(-?\d{1,3}(?:\.\d{3})*,\d{2})', context_after)
                    if amounts_near:
                        importo = _to_float(amounts_near[0])
    
    data["pagamento"] = {
        "modalita": modalita,
        "scadenza": scadenza,
        "importo": importo,
    }

    return data
