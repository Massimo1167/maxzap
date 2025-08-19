#!/usr/bin/env python3
"""
Progeo Delivery Note Tester - Tool di test e debug per pyzap.plugins.progeo_delivery_note.py

Uso:
    python progeo_delivery_note_tester.py [files...] [flags]

Esempi:
    python progeo_delivery_note_tester.py "2025-01-03 Bolla BB25-000264 PROGEO.pdf" --debug
    python progeo_delivery_note_tester.py --debug-all  # usa lista predefinita
    python progeo_delivery_note_tester.py *.pdf --compare-legacy -o progeo_test_results.csv

Flags:
    --debug              Debug completo (estrazione testo, parsing, articoli)
    --debug-all          Debug con lista predefinita file
    -o filename.csv      Specifica file output CSV (default: progeo_delivery_note_test_results.csv)
    --compare-legacy     Confronto con parser legacy (progeo_delivery_note_legacy.py)
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
    from pyzap.plugins.progeo_delivery_note import ProgeoDeliveryNoteAction
except ImportError as e:
    print(f"ERRORE: Impossibile importare pyzap.plugins.progeo_delivery_note: {e}")
    sys.exit(1)

# Importa direttamente le librerie per estrazione PDF
try:
    from pdfminer.high_level import extract_text
except ImportError:
    print("ERRORE: pdfminer.six non installato. Esegui: pip install pdfminer.six")
    sys.exit(1)

# Parser legacy per confronto (se disponibile)
try:
    import progeo_delivery_note_legacy
    legacy_available = True
except ImportError:
    legacy_available = False

# Lista predefinita di file PDF per test (se non specificati file)
DEFAULT_TEST_FILES = [
    "2025-01-03 Bolla BB25-000264 PROGEO.pdf",
    "2025-01-03 Bolla BB25-000265 PROGEO.pdf", 
    "2025-01-04 Bolla BB25-000270 PROGEO.pdf",
]


def extract_delivery_note_main(pdf_path: str, debug: bool = False) -> Dict[str, Any]:
    """Estrae dati delivery note usando pyzap.plugins.progeo_delivery_note con debug opzionale"""
    if debug:
        print(f"DEBUG EXTRACT_DELIVERY_NOTE: Processing {pdf_path}")
    
    try:
        # Crea action con parametri
        params = {
            'pdf_path': pdf_path,
            'output_dir': None,  # Non salvare file durante test
            'debug': debug
        }
        action = ProgeoDeliveryNoteAction(params)
        
        # Esegui parsing
        input_data = {'test_mode': True}
        result = action.execute(input_data)
        
        if debug:
            print(f"DEBUG MAIN RESULT: {result.get('parsed_successfully', False)}")
            if result.get('parsed_successfully'):
                print(f"DEBUG DOCUMENTO: {result.get('documento_numero')} - {result.get('documento_data')}")
                print(f"DEBUG ARTICOLI: {result.get('numero_articoli', 0)} found")
        
        return result
        
    except Exception as e:
        if debug:
            print(f"DEBUG: Main parser failed: {e}")
            import traceback
            traceback.print_exc()
        return {'parsed_successfully': False, 'error': str(e)}


def extract_delivery_note_legacy(pdf_path: str) -> Dict[str, Any] | None:
    """Estrae dati delivery note usando il parser legacy se disponibile"""
    if not legacy_available:
        return None
    
    try:
        # Simula lo stesso interfaccia del main parser
        params = {
            'pdf_path': pdf_path,
            'output_dir': None,
            'debug': False
        }
        action = progeo_delivery_note_legacy.ProgeoDeliveryNoteAction(params)
        
        input_data = {'test_mode': True}
        result = action.execute(input_data)
        
        return result
        
    except Exception as e:
        print(f"DEBUG: Legacy parser failed: {e}")
        return None


def flatten_for_csv(parsed: Dict[str, Any], pdf_path: str, *, parser_name: str) -> Dict[str, str]:
    """Converte il risultato parsing in formato CSV flat"""
    def g(key: str, default: str = "") -> str:
        """Get value with default"""
        value = parsed.get(key, default)
        return str(value) if value is not None else default

    # Estrai peso totale se è un float
    peso_totale = parsed.get('peso_totale_articoli', '')
    if isinstance(peso_totale, (int, float)):
        peso_totale = f"{peso_totale:.2f}"
    
    return {
        "parser": parser_name,
        "file": pdf_path,
        "parsed_successfully": g("parsed_successfully"),
        "documento_tipo": g("documento_tipo"),
        "documento_numero": g("documento_numero"),
        "documento_data": g("documento_data"),
        "documento_pagina": g("documento_pagina"),
        "mittente_denominazione": g("mittente_denominazione"),
        "mittente_piva": g("mittente_piva"),
        "mittente_indirizzo": g("mittente_indirizzo"),
        "mittente_citta": g("mittente_citta"),
        "destinatario_denominazione": g("destinatario_denominazione"),
        "destinatario_piva": g("destinatario_piva"),
        "destinatario_codice_cliente": g("destinatario_codice_cliente"),
        "destinatario_indirizzo": g("destinatario_indirizzo"),
        "destinatario_citta": g("destinatario_citta"),
        "trasporto_vettore": g("trasporto_vettore")[:100],  # Trunc per CSV
        "trasporto_data_ritiro": g("trasporto_data_ritiro"),
        "trasporto_ora_ritiro": g("trasporto_ora_ritiro"),
        "trasporto_peso_netto_kg": g("trasporto_peso_netto_kg"),
        "trasporto_tipo": g("trasporto_tipo"),
        "numero_ordine": g("numero_ordine"),
        "riferimento_ordine_cliente": g("riferimento_ordine_cliente"),
        "riferimento_carico": g("riferimento_carico"),
        "metodo_pagamento": g("metodo_pagamento")[:50],  # Trunc per CSV
        "causale": g("causale"),
        "numero_articoli": g("numero_articoli"),
        "peso_totale_articoli": peso_totale,
        "articoli_descrizione": g("articoli_descrizione")[:100],  # Trunc per CSV
        "error": g("error")[:100] if not parsed.get('parsed_successfully') else "",
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


def show_comparison(main_row: Dict[str, str], legacy_row: Dict[str, str]):
    """Mostra confronto tra parser main e legacy"""
    important_fields = [
        "documento_numero", "documento_data", "mittente_denominazione",
        "destinatario_denominazione", "destinatario_piva", "numero_articoli",
        "peso_totale_articoli", "trasporto_peso_netto_kg"
    ]
    
    differences = []
    for field in important_fields:
        main_val = main_row.get(field, "")
        legacy_val = legacy_row.get(field, "")
        if main_val != legacy_val:
            differences.append((field, main_val, legacy_val))
    
    if differences:
        print(f"\nDIFFERENZE TROVATE ({len(differences)}):")
        for field, main_val, legacy_val in differences:
            print(f"  {field}:")
            print(f"    Main:   {repr(main_val)}")
            print(f"    Legacy: {repr(legacy_val)}")
    else:
        print("\nNESSUNA DIFFERENZA tra main e legacy parser")


def main():
    parser = argparse.ArgumentParser(
        description="Tester per pyzap.plugins.progeo_delivery_note.py - Estrazione dati delivery note Progeo",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    
    parser.add_argument("files", nargs="*", 
                       help="File PDF da processare (se non specificati, usa lista predefinita)")
    parser.add_argument("--debug", action="store_true",
                       help="Debug completo (estrazione testo, parsing, articoli)")
    parser.add_argument("--debug-all", action="store_true", 
                       help="Debug con lista predefinita file")
    parser.add_argument("-o", "--output", default="progeo_delivery_note_test_results.csv",
                       help="File output CSV (default: progeo_delivery_note_test_results.csv)")
    parser.add_argument("--compare-legacy", action="store_true",
                       help="Confronto con parser legacy (progeo_delivery_note_legacy.py)")
    
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
        # Usa lista predefinita o tutti i file PDF Progeo
        print("Nessun file specificato, cerco file Progeo...")
        
        # Cerca automaticamente file con pattern Progeo
        progeo_patterns = [
            "*PROGEO*.pdf",
            "*BB25-*.pdf", 
            "*Bolla*.pdf"
        ]
        
        for pattern in progeo_patterns:
            matches = glob.glob(pattern)
            for match in matches:
                if match not in files_to_process:
                    files_to_process.append(match)
        
        if not files_to_process:
            print("Nessun file Progeo trovato, uso lista predefinita:")
            for f in DEFAULT_TEST_FILES:
                if os.path.exists(f):
                    files_to_process.append(f)
                    print(f"  - {f}")
                else:
                    print(f"  - {f} (NON TROVATO)")
        else:
            print(f"Trovati {len(files_to_process)} file Progeo:")
            for f in files_to_process:
                print(f"  - {f}")
    
    if not files_to_process:
        print("Nessun file da processare!")
        return
    
    # Verifica disponibilità parser legacy se richiesto confronto
    if args.compare_legacy and not legacy_available:
        print("ATTENZIONE: --compare-legacy richiesto ma progeo_delivery_note_legacy.py non disponibile")
        print("Crea progeo_delivery_note_legacy.py nella directory corrente per abilitare il confronto")
        args.compare_legacy = False
    
    # Processamento file
    rows = []
    for pth in files_to_process:
        print(f"\n=== PROCESSANDO: {os.path.basename(pth)} ===")
        
        try:
            # Parser principale (pyzap.plugins.progeo_delivery_note)
            parsed = extract_delivery_note_main(pth, debug=args.debug or args.debug_all)
            
            if parsed.get('parsed_successfully'):
                print(f"\n=== RISULTATI PARSING per {os.path.basename(pth)} ===")
                print(f"documento_tipo: {repr(parsed.get('documento_tipo'))}")
                print(f"documento_numero: {repr(parsed.get('documento_numero'))}")
                print(f"documento_data: {repr(parsed.get('documento_data'))}")
                print(f"mittente: {repr(parsed.get('mittente_denominazione'))}")
                print(f"destinatario: {repr(parsed.get('destinatario_denominazione'))}")
                print(f"numero_articoli: {parsed.get('numero_articoli', 0)}")
                print(f"peso_totale: {parsed.get('peso_totale_articoli', 'N/A')} TN")
                
                main_row = flatten_for_csv(parsed, pth, parser_name="main")
                rows.append(main_row)
                
                # Confronto con parser legacy (se richiesto)
                if args.compare_legacy:
                    legacy = extract_delivery_note_legacy(pth)
                    if legacy and legacy.get('parsed_successfully'):
                        legacy_row = flatten_for_csv(legacy, pth, parser_name="legacy")
                        rows.append(legacy_row)
                        
                        # Mostra differenze principali
                        show_comparison(main_row, legacy_row)
                    else:
                        print("\nLegacy parser: Nessun risultato o fallito")
            else:
                error = parsed.get('error', 'Errore sconosciuto')
                print(f"Parsing fallito: {error}")
                
                # Aggiungi riga con errore
                error_row = flatten_for_csv(parsed, pth, parser_name="main")
                rows.append(error_row)
                
        except Exception as e:
            print(f"ERRORE durante il processing di {pth}: {e}")
            if args.debug or args.debug_all:
                import traceback
                traceback.print_exc()
    
    # Scrittura CSV
    if rows:
        write_csv(rows, args.output, sep=";")
        print(f"\nCSV scritto: {args.output} — righe: {len(rows)}")
        
        # Riepilogo finale
        main_rows = [r for r in rows if r['parser'] == 'main']
        successful_rows = [r for r in main_rows if r['parsed_successfully'] == 'True']
        
        print(f"\n=== RIEPILOGO TOTALE - {len(main_rows)} DELIVERY NOTE PROCESSATE ===")
        print(f"SUCCESSI: {len(successful_rows)}/{len(main_rows)}")
        
        for i, row in enumerate(successful_rows, 1):
            filename = row.get('file', 'N/A')
            if '\\' in filename:
                filename = filename.split('\\')[-1]
            elif '/' in filename:
                filename = filename.split('/')[-1]
                
            print(f"\nDELIVERY NOTE #{i}: {filename}")
            print(f"  Numero:      {row.get('documento_numero', 'N/A')}")
            print(f"  Data:        {row.get('documento_data', 'N/A')}")
            print(f"  Destinatario: {row.get('destinatario_denominazione', 'N/A')}")
            print(f"  Articoli:    {row.get('numero_articoli', 'N/A')}")
            print(f"  Peso Tot:    {row.get('peso_totale_articoli', 'N/A')} TN")
        
        # Mostra errori se ci sono
        failed_rows = [r for r in main_rows if r['parsed_successfully'] != 'True']
        if failed_rows:
            print(f"\n=== ERRORI ({len(failed_rows)}) ===")
            for row in failed_rows:
                filename = os.path.basename(row.get('file', 'N/A'))
                error = row.get('error', 'N/A')
                print(f"  {filename}: {error}")
        
        print("\n=== FINE ELABORAZIONE ===")
    else:
        print("Nessun dato da scrivere nel CSV")


if __name__ == "__main__":
    main()