#!/usr/bin/env python3
"""Debug script per analizzare i token estratti"""

import sys
import os
import re

# Aggiungi il percorso del modulo pyzap
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'pyzap'))

def debug_token_extraction():
    """Debug dell'estrazione token dal testo documento"""
    
    # Testo della sezione documento come estratto dal parsing
    sample_text = """Tipologia documento
TD24 fattura differita di cui all'art.21, comma 4, 
terzo periodo lett.a) DPR 633/72
3097
23-07-2025
0000000"""
    
    # Simula la logica di pulizia delle righe
    lines = sample_text.split('\n')
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
    
    print("DEBUG TOKEN EXTRACTION:")
    print("=" * 50)
    print(f"Original text:\n{sample_text}")
    print(f"\nCleaned lines: {cleaned_lines}")
    print(f"\nCombined text: '{hz_clean}'")
    print(f"\nTokens: {tokens}")
    print(f"Total tokens: {len(tokens)}")
    
    # Find date
    DATE_RE = re.compile(r"\b(\d{4}-\d{2}-\d{2}|\d{2}-\d{2}-\d{4}|\d{2}/\d{2}/\d{4})\b")
    date_idx = None
    data_doc = None
    
    for i, t in enumerate(tokens):
        if DATE_RE.match(t):
            data_doc = t
            date_idx = i
            break
    
    print(f"\nDate found: '{data_doc}' at index {date_idx}")
    
    # Debug numero extraction
    if date_idx is not None and date_idx > 0:
        potential_numero = tokens[date_idx - 1]
        print(f"\nToken before date: '{potential_numero}'")
        
        # Check filters
        def _is_law_token(tok: str) -> bool:
            if "/" in tok and re.fullmatch(r"\d{3}/\d{2}", tok):
                return True
            return tok in {"633/72", "600/73", "600/1973"}
        
        check1 = not re.search(r"^(DPR|lett\.|a\)|b\)|c\))$", potential_numero, re.IGNORECASE)
        check2 = not re.search(r"^\d{3}/\d{2}$", potential_numero)
        check3 = potential_numero not in ["DPR", "633/72"]
        check4 = not _is_law_token(potential_numero)
        
        print(f"Check 1 (not DPR/lett): {check1}")
        print(f"Check 2 (not 633/72 format): {check2}")
        print(f"Check 3 (not in ['DPR', '633/72']): {check3}")
        print(f"Check 4 (not law token): {check4}")
        print(f"Overall valid: {check1 and check2 and check3 and check4}")
    
    # Show context around date
    if date_idx is not None:
        start = max(0, date_idx - 3)
        end = min(len(tokens), date_idx + 3)
        print(f"\nContext around date:")
        for i in range(start, end):
            marker = " -> " if i == date_idx else "    "
            print(f"{marker}[{i}]: '{tokens[i]}'")

if __name__ == "__main__":
    debug_token_extraction()