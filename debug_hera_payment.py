#!/usr/bin/env python3
"""
Debug specifico per il file HERA con problema pagamento_importo
"""

import os
from PyPDF2 import PdfReader
from pdfminer.high_level import extract_text
from pyzap.pdf_invoice import parse_invoice_text

def debug_hera_payment():
    pdf_path = "2025-07-23 Fattura 112505493391 HERA S.p.A..pdf"
    print(f"=== Debugging HERA payment issue for {pdf_path} ===")
    
    if not os.path.exists(pdf_path):
        print(f"File not found: {pdf_path}")
        return
    
    # PyPDF2 extraction
    with open(pdf_path, 'rb') as f:
        reader = PdfReader(f)
        pypdf2_text = ''
        for page in reader.pages:
            pypdf2_text += page.extract_text() or ''
    
    # PDFMiner extraction  
    pdfminer_text = extract_text(pdf_path)
    
    for name, text in [("PyPDF2", pypdf2_text), ("PDFMiner", pdfminer_text)]:
        print(f"\n--- {name} Payment Analysis ---")
        
        # Look for payment section
        import re
        
        # Find MP section
        mp_section = re.search(r'MP\d{2}.*?(?=Allegati|$)', text, re.DOTALL | re.IGNORECASE)
        if mp_section:
            print(f"MP section: {repr(mp_section.group(0)[:200])}")
            
            # Look for amounts in MP section
            amounts = re.findall(r'(\d{1,3}(?:\.\d{3})*,\d{2})', mp_section.group(0))
            print(f"Amounts in MP section: {amounts}")
            
        # Look for data scadenza
        scadenza_match = re.search(r"Data scadenza\s+([\d\-/]+)", text)
        if scadenza_match:
            print(f"Found scadenza: {scadenza_match.group(1)}")
        else:
            print("No scadenza found")
        
        # Test full parser
        result = parse_invoice_text(text)
        payment = result.get('pagamento', {})
        print(f"Parser results:")
        print(f"  modalita: {repr(payment.get('modalita'))}")
        print(f"  scadenza: {repr(payment.get('scadenza'))}")
        print(f"  importo: {repr(payment.get('importo'))}")

if __name__ == "__main__":
    debug_hera_payment()