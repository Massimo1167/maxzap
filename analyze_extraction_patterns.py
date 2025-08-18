#!/usr/bin/env python3
"""
Analizza pattern di estrazione per PyPDF2 vs pdfminer.six
"""

import os
import glob
from PyPDF2 import PdfReader
from pdfminer.high_level import extract_text
from pyzap.pdf_invoice import parse_invoice_text

def analyze_file(pdf_path):
    """Analizza un singolo file PDF con entrambi i metodi"""
    print(f"\n=== {os.path.basename(pdf_path)} ===")
    
    try:
        # Estrazione PyPDF2
        with open(pdf_path, 'rb') as f:
            reader = PdfReader(f)
            pypdf2_text = ''
            for page in reader.pages:
                pypdf2_text += page.extract_text() or ''
        
        # Estrazione pdfminer
        pdfminer_text = extract_text(pdf_path)
        
        # Parsing con entrambi
        result_pypdf2 = parse_invoice_text(pypdf2_text)
        result_pdfminer = parse_invoice_text(pdfminer_text)
        
        # Confronta campi chiave
        fields = {
            'documento_numero': ('documento', 'numero'),
            'documento_tipo': ('documento', 'tipo'),
            'documento_data': ('documento', 'data'),
            'pagamento_modalita': ('pagamento', 'modalita'),
            'pagamento_scadenza': ('pagamento', 'scadenza'),
            'pagamento_importo': ('pagamento', 'importo'),
            'fornitore_denominazione': ('fornitore', 'denominazione'),
            'totale_documento': ('riepilogo_importi', 'totale')
        }
        
        differences = []
        for field_name, (section, key) in fields.items():
            val_pypdf2 = result_pypdf2.get(section, {}).get(key)
            val_pdfminer = result_pdfminer.get(section, {}).get(key)
            
            if val_pypdf2 != val_pdfminer:
                differences.append({
                    'field': field_name,
                    'pypdf2': val_pypdf2,
                    'pdfminer': val_pdfminer
                })
        
        if differences:
            print("DIFFERENZE TROVATE:")
            for diff in differences:
                print(f"  {diff['field']}:")
                print(f"    PyPDF2:   {repr(diff['pypdf2'])}")
                print(f"    PDFMiner: {repr(diff['pdfminer'])}")
        else:
            print("NESSUNA DIFFERENZA - Risultati identici")
            
        return {
            'file': os.path.basename(pdf_path),
            'differences': differences,
            'pypdf2_length': len(pypdf2_text),
            'pdfminer_length': len(pdfminer_text),
            'pypdf2_result': result_pypdf2,
            'pdfminer_result': result_pdfminer
        }
        
    except Exception as e:
        print(f"ERRORE: {e}")
        return {'file': os.path.basename(pdf_path), 'error': str(e)}

def main():
    # Trova tutti i PDF
    pdf_files = glob.glob("*.pdf")
    pdf_files.sort()
    
    print(f"Analizzando {len(pdf_files)} file PDF...")
    
    results = []
    field_stats = {}
    
    for pdf_file in pdf_files:
        result = analyze_file(pdf_file)
        results.append(result)
        
        # Raccoglie statistiche per campo
        if 'differences' in result:
            for diff in result['differences']:
                field = diff['field']
                if field not in field_stats:
                    field_stats[field] = {'pypdf2_better': 0, 'pdfminer_better': 0, 'total_differences': 0}
                field_stats[field]['total_differences'] += 1
    
    # Statistiche finali
    print("\n" + "="*60)
    print("STATISTICHE FINALI")
    print("="*60)
    
    total_files = len([r for r in results if 'differences' in r])
    files_with_differences = len([r for r in results if 'differences' in r and r['differences']])
    
    print(f"File analizzati: {total_files}")
    print(f"File con differenze: {files_with_differences}")
    print(f"File identici: {total_files - files_with_differences}")
    
    if field_stats:
        print(f"\nCampi con differenze:")
        for field, stats in field_stats.items():
            print(f"  {field}: {stats['total_differences']} differenze")
    
    # Identifica pattern comuni
    print(f"\nPattern comuni:")
    document_number_issues = [r for r in results if 'differences' in r and 
                            any(d['field'] == 'documento_numero' for d in r['differences'])]
    payment_issues = [r for r in results if 'differences' in r and 
                     any(d['field'] == 'pagamento_modalita' for d in r['differences'])]
    
    print(f"  - Problemi documento_numero: {len(document_number_issues)} file")
    print(f"  - Problemi pagamento_modalita: {len(payment_issues)} file")

if __name__ == "__main__":
    main()