#!/usr/bin/env python3
"""
Debug script per analizzare le differenze di layout tra PyPDF2 e pdfminer.six
"""

import os
import re
from PyPDF2 import PdfReader
from pdfminer.high_level import extract_text
from pyzap.pdf_invoice import parse_invoice_text

def analyze_specific_file(pdf_path):
    """Analizza un file specifico per capire le differenze di layout"""
    print(f"\n=== ANALYZING {os.path.basename(pdf_path)} ===")
    
    # Estrazione PyPDF2
    with open(pdf_path, 'rb') as f:
        reader = PdfReader(f)
        pypdf2_text = ''
        for page in reader.pages:
            pypdf2_text += page.extract_text() or ''
    
    # Estrazione pdfminer
    pdfminer_text = extract_text(pdf_path)
    
    print(f"PyPDF2 text length: {len(pypdf2_text)}")
    print(f"PDFMiner text length: {len(pdfminer_text)}")
    
    # Cerca la sezione documento in entrambi
    print("\n--- DOCUMENTO SECTION ANALYSIS ---")
    
    # Cerca pattern pagamento_modalita
    print("\n--- PAGAMENTO_MODALITA ANALYSIS ---")
    pypdf2_mp = re.search(r'\bMP\d{2}\s+(\w+)', pypdf2_text)
    pdfminer_mp = re.search(r'\bMP\d{2}\s+(\w+)', pdfminer_text)
    
    print(f"PyPDF2 MP pattern: {pypdf2_mp.group(0) if pypdf2_mp else 'NOT FOUND'}")
    print(f"PDFMiner MP pattern: {pdfminer_mp.group(0) if pdfminer_mp else 'NOT FOUND'}")
    
    # Analizza il contesto intorno ai pattern MP
    if pypdf2_mp:
        start = max(0, pypdf2_mp.start() - 100)
        end = min(len(pypdf2_text), pypdf2_mp.end() + 100)
        print(f"\nPyPDF2 context around MP:\n{repr(pypdf2_text[start:end])}")
    
    if pdfminer_mp:
        start = max(0, pdfminer_mp.start() - 100)
        end = min(len(pdfminer_text), pdfminer_mp.end() + 100)
        print(f"\nPDFMiner context around MP:\n{repr(pdfminer_text[start:end])}")
    
    # Cerca pattern numero documento
    print("\n--- NUMERO DOCUMENTO ANALYSIS ---")
    
    # Pattern per numeri con prefisso V2-
    pypdf2_v2 = re.search(r'V2-\d+', pypdf2_text)
    pdfminer_v2 = re.search(r'V2-\d+', pdfminer_text)
    
    print(f"PyPDF2 V2- pattern: {pypdf2_v2.group(0) if pypdf2_v2 else 'NOT FOUND'}")
    print(f"PDFMiner V2- pattern: {pdfminer_v2.group(0) if pdfminer_v2 else 'NOT FOUND'}")
    
    # Analizza struttura documento header
    print("\n--- DOCUMENTO HEADER STRUCTURE ---")
    
    # Cerca header Tipologia documento
    tip_pypdf2 = re.search(r'Tipologia\s+documento.*?(\d{2}-\d{2}-\d{4})', pypdf2_text, re.DOTALL)
    tip_pdfminer = re.search(r'Tipologia\s+documento.*?(\d{2}-\d{2}-\d{4})', pdfminer_text, re.DOTALL)
    
    if tip_pypdf2:
        print(f"\nPyPDF2 Tipologia->Data section:\n{repr(tip_pypdf2.group(0))}")
    
    if tip_pdfminer:
        print(f"\nPDFMiner Tipologia->Data section:\n{repr(tip_pdfminer.group(0))}")
    
    # Parse con entrambi i metodi
    print("\n--- PARSING RESULTS ---")
    result_pypdf2 = parse_invoice_text(pypdf2_text)
    result_pdfminer = parse_invoice_text(pdfminer_text)
    
    doc_pypdf2 = result_pypdf2.get('documento', {})
    doc_pdfminer = result_pdfminer.get('documento', {})
    
    print(f"PyPDF2 numero: {repr(doc_pypdf2.get('numero'))}")
    print(f"PDFMiner numero: {repr(doc_pdfminer.get('numero'))}")
    
    pag_pypdf2 = result_pypdf2.get('pagamento', {})
    pag_pdfminer = result_pdfminer.get('pagamento', {})
    
    print(f"PyPDF2 modalita: {repr(pag_pypdf2.get('modalita'))}")
    print(f"PDFMiner modalita: {repr(pag_pdfminer.get('modalita'))}")

def main():
    # Testa alcuni file specifici che hanno differenze note
    test_files = [
        "2025-08-12 Fattura V2-250039161 PROGEO SCA.pdf",  # Ha problema numero documento
        "2025-07-30 Fattura TD01 RIVI PAOLO & C. SAS.pdf",  # Ha problema numero documento + modalita
        "2025-07-23 Fattura 112505418437 HERA S.p.A..pdf",  # Ha solo problema modalita
    ]
    
    for filename in test_files:
        if os.path.exists(filename):
            analyze_specific_file(filename)
        else:
            print(f"File non trovato: {filename}")

if __name__ == "__main__":
    main()