#!/usr/bin/env python3
"""
PDF Invoice Tester - Tool di test e debug per pyzap.pdf_invoice.py

Uso:
    python pdf_invoice_tester.py [files...] [flags]

Esempi:
    python pdf_invoice_tester.py "2025-08-12 Fattura V2-250039161 PROGEO SCA.pdf" --debug
    python pdf_invoice_tester.py --debug-headers  # usa lista predefinita
    python pdf_invoice_tester.py *.pdf --compare-native -o test_results.csv

Flags:
    --debug              Debug completo (estrazione testo, parsing, token analysis)
    --debug-headers      Debug specifico solo per header DOCUMENTO  
    -o filename.csv      Specifica file output CSV (default: pdf_invoice_test_results.csv)
    --compare-native     Confronto con parser legacy (pdf_invoice_legacy.py)
"""

import argparse
import csv
import os
import sys
from typing import Any, Dict, List
import glob

# Estensione percorso per importare il modulo pyzap
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from pyzap.pdf_invoice import parse_invoice_text
except ImportError as e:
    print(f"ERRORE: Impossibile importare pyzap.pdf_invoice: {e}")
    sys.exit(1)

# Importa direttamente le librerie per estrazione PDF
try:
    from pdfminer.high_level import extract_text
except ImportError:
    print("ERRORE: pdfminer.six non installato. Esegui: pip install pdfminer.six")
    sys.exit(1)

# Parser legacy per confronto (se disponibile)
try:
    import pdf_invoice_legacy
    legacy_available = True
except ImportError:
    legacy_available = False

# Lista predefinita di file PDF per test (se non specificati file)
DEFAULT_TEST_FILES = [
    "2025-07-24 Fattura 250035610 PROGEO SCA.pdf",
    "2025-07-21 Fattura 20788_2025_G1 DUSTY RENDERING S.R.L..pdf", 
    "2025-07-30 Fattura TD01 RIVI PAOLO & C. SAS.pdf",
    "2025-07-31 Fattura 2632_00 EMMEDIELLE S.R.L..pdf",
    "2025-07-31 Fattura B002079 GARC AMBIENTE SPA SB.pdf"
]


def _extract_text_pdf_native(pdf_path: str) -> str:
    """Estrae testo dal PDF usando pdfminer.six"""
    try:
        return extract_text(pdf_path)
    except Exception as e:
        print(f"Errore nell'estrazione del testo da {pdf_path}: {e}")
        return ""


def extract_invoice_main(pdf_path: str, debug: bool = False, debug_headers: bool = False) -> Dict[str, Any]:
    """Estrae dati fattura usando pyzap.pdf_invoice con debug opzionale"""
    if debug:
        print(f"DEBUG EXTRACT_INVOICE: Processing {pdf_path}")
    
    # Estrazione testo PDF
    text = _extract_text_pdf_native(pdf_path)
    if not text:
        if debug:
            print("DEBUG: Nessun testo estratto dal PDF")
        return {}
    
    if debug:
        print(f"DEBUG NATIVE TEXT: {len(text)} chars extracted")
        print(f"DEBUG NATIVE PREVIEW: {repr(text[:200])}...")
    
    # Parsing con debug
    debug_enabled = debug or debug_headers
    result = parse_invoice_text(text, debug=debug_enabled)
    
    return result


def extract_invoice_legacy(pdf_path: str) -> Dict[str, Any] | None:
    """Estrae dati fattura usando il parser legacy se disponibile"""
    if not legacy_available:
        return None
    
    text = _extract_text_pdf_native(pdf_path)
    if not text:
        return None
    
    try:
        return pdf_invoice_legacy.parse_invoice_text(text)
    except Exception as e:
        print(f"DEBUG: Legacy parser failed: {e}")
        return None


def flatten_for_csv(parsed: Dict[str, Any], pdf_path: str, *, parser_name: str) -> Dict[str, str]:
    """Converte il risultato parsing in formato CSV flat"""
    def g(*keys, default="") -> str:
        cur: Any = parsed
        for k in keys:
            if not isinstance(cur, dict):
                return default
            cur = cur.get(k)
            if cur is None:
                return default
        return str(cur)

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
        # Debug header detection (se presente)
        "debug_header_detected": g("debug_header", "detected"),
        "debug_header_start": g("debug_header", "header_start"),
        "debug_header_end": g("debug_header", "header_end"),
        "debug_header_lines": "|".join(parsed.get("debug_header", {}).get("header_lines", [])),
        "debug_found_labels": g("debug_header", "found_labels"),
    }


def write_csv(rows: List[Dict[str, str]], output_file: str, sep: str = ";"):
    """Scrive risultati in formato CSV"""
    if not rows:
        print("Nessun dato da scrivere nel CSV")
        return
    
    fieldnames = rows[0].keys()
    with open(output_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter=sep)
        writer.writeheader()
        writer.writerows(rows)


def main():
    parser = argparse.ArgumentParser(
        description="Tester per pyzap.pdf_invoice.py - Estrazione dati fatture elettroniche",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    
    parser.add_argument("files", nargs="*", 
                       help="File PDF da processare (se non specificati, usa lista predefinita)")
    parser.add_argument("--debug", action="store_true",
                       help="Debug completo (estrazione testo, parsing, token analysis)")
    parser.add_argument("--debug-headers", action="store_true", 
                       help="Debug specifico solo per header DOCUMENTO")
    parser.add_argument("-o", "--output", default="pdf_invoice_test_results.csv",
                       help="File output CSV (default: pdf_invoice_test_results.csv)")
    parser.add_argument("--compare-native", action="store_true",
                       help="Confronto con parser legacy (pdf_invoice_legacy.py)")
    
    args = parser.parse_args()
    
    # Determina file da processare
    files_to_process = []
    if args.files:
        for pattern in args.files:
            if "*" in pattern or "?" in pattern:
                # Espansione glob pattern
                expanded = glob.glob(pattern)
                if expanded:
                    files_to_process.extend(expanded)
                else:
                    print(f"File non trovato: {pattern}")
            else:
                if os.path.exists(pattern):
                    files_to_process.append(pattern)
                else:
                    print(f"File non trovato: {pattern}")
    else:
        # Usa lista predefinita
        print("Nessun file specificato, uso lista predefinita:")
        for f in DEFAULT_TEST_FILES:
            if os.path.exists(f):
                files_to_process.append(f)
                print(f"  - {f}")
            else:
                print(f"  - {f} (NON TROVATO)")
    
    if not files_to_process:
        print("Nessun file da processare!")
        return
    
    # Verifica disponibilità parser legacy se richiesto confronto
    if args.compare_native and not legacy_available:
        print("ATTENZIONE: --compare-native richiesto ma pdf_invoice_legacy.py non disponibile")
        print("Crea pdf_invoice_legacy.py nella directory corrente per abilitare il confronto")
        args.compare_native = False
    
    # Processamento file
    rows = []
    for pth in files_to_process:
        print(f"\n=== PROCESSANDO: {os.path.basename(pth)} ===")
        
        try:
            # Parser principale (pyzap.pdf_invoice)
            parsed = extract_invoice_main(pth, debug=args.debug, debug_headers=args.debug_headers)
            
            if parsed:
                print(f"\n=== RISULTATI PARSING per {os.path.basename(pth)} ===")
                doc = parsed.get("documento", {})
                print(f"documento_tipo: {repr(doc.get('tipo'))}")
                print(f"documento_numero: {repr(doc.get('numero'))}")
                print(f"documento_data: {repr(doc.get('data'))}")
                print(f"documento_codice_destinatario: {repr(doc.get('codice_destinatario'))}")
                
                rows.append(flatten_for_csv(parsed, pth, parser_name="main"))
                
                # Confronto con parser legacy (se richiesto)
                if args.compare_native:
                    legacy = extract_invoice_legacy(pth)
                    if legacy:
                        rows.append(flatten_for_csv(legacy, pth, parser_name="legacy"))
                        
                        # Mostra differenze principali
                        main_numero = doc.get('numero', '')
                        legacy_numero = legacy.get('documento', {}).get('numero', '')
                        if main_numero != legacy_numero:
                            print(f"\nDIFFERENZA NUMERO DOCUMENTO:")
                            print(f"  Main:   {repr(main_numero)}")
                            print(f"  Legacy: {repr(legacy_numero)}")
                    else:
                        print("\nLegacy parser: Nessun risultato")
            else:
                print("Nessun dato estratto dal parsing")
                
        except Exception as e:
            print(f"ERRORE durante il processing di {pth}: {e}")
            import traceback
            traceback.print_exc()
    
    # Scrittura CSV
    if rows:
        write_csv(rows, args.output, sep=";")
        print(f"\nCSV scritto: {args.output} — righe: {len(rows)}")
        
        # Riepilogo finale
        print(f"\n=== RIEPILOGO TOTALE - {len([r for r in rows if r['parser'] == 'main'])} FATTURE PROCESSATE ===")
        for i, row in enumerate([r for r in rows if r['parser'] == 'main'], 1):
            filename = row.get('file', 'N/A')
            if '\\' in filename:
                filename = filename.split('\\')[-1]
            elif '/' in filename:
                filename = filename.split('/')[-1]
                
            print(f"\nFATTURA #{i}: {filename}")
            print(f"  Tipologia: {row.get('documento_tipologia', 'N/A')}")
            print(f"  Numero:    {row.get('documento_numero', 'N/A')}")
            print(f"  Data:      {row.get('documento_data', 'N/A')}")
            print(f"  Destinatario: {row.get('documento_codice_destinatario', 'N/A')}")
        
        print("\n=== FINE ELABORAZIONE ===")
    else:
        print("Nessun dato da scrivere nel CSV")


if __name__ == "__main__":
    main()