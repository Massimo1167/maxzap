#!/usr/bin/env python3
"""
Debug specifico per pagamento_scadenza e pagamento_importo
"""

import os
import re
from PyPDF2 import PdfReader
from pdfminer.high_level import extract_text
from pyzap.pdf_invoice import parse_invoice_text

def debug_payment_details(pdf_path):
    print(f"=== Debugging payment details for {pdf_path} ===")
    
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
        payment_section = re.search(r'Data scadenza.*?(\d{2}-\d{2}-\d{4}).*?([\d\.,]+)', text, re.DOTALL)
        if payment_section:
            print(f"Payment section match: {repr(payment_section.group(0))}")
            print(f"Scadenza: {payment_section.group(1)}")
            print(f"Importo: {payment_section.group(2)}")
        else:
            print("Payment section not found with current pattern")
            
            # Look for alternative patterns
            date_matches = re.findall(r'\d{2}-\d{2}-\d{4}', text)
            print(f"All dates found: {date_matches}")
            
            amount_matches = re.findall(r'[\d\.,]+', text)
            print(f"Sample amounts: {amount_matches[-10:] if len(amount_matches) > 10 else amount_matches}")
        
        # Test full parser
        result = parse_invoice_text(text)
        payment = result.get('pagamento', {})
        print(f"Parser results:")
        print(f"  modalita: {repr(payment.get('modalita'))}")
        print(f"  scadenza: {repr(payment.get('scadenza'))}")
        print(f"  importo: {repr(payment.get('importo'))}")

def main():
    # Test the file that has payment details differences
    test_file = "2025-07-31 Fattura 2632_00 EMMEDIELLE S.R.L..pdf"
    if os.path.exists(test_file):
        debug_payment_details(test_file)
    else:
        print(f"File not found: {test_file}")
        # Try to find any PDF file
        import glob
        pdfs = glob.glob("*.pdf")
        if pdfs:
            print(f"Testing with first available PDF: {pdfs[0]}")
            debug_payment_details(pdfs[0])

if __name__ == "__main__":
    main()