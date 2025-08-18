#!/usr/bin/env python3
"""
Test specifico per V2- document numbers
"""

import os
from PyPDF2 import PdfReader
from pdfminer.high_level import extract_text
from pyzap.pdf_invoice import parse_invoice_text

def test_v2_extraction(pdf_path):
    print(f"=== Testing V2- extraction for {pdf_path} ===")
    
    # PyPDF2 extraction
    with open(pdf_path, 'rb') as f:
        reader = PdfReader(f)
        pypdf2_text = ''
        for page in reader.pages:
            pypdf2_text += page.extract_text() or ''
    
    # PDFMiner extraction  
    pdfminer_text = extract_text(pdf_path)
    
    print("PyPDF2 V2- search:")
    print(f"  V2- found: {'V2-' in pypdf2_text}")
    if 'V2-' in pypdf2_text:
        import re
        v2_matches = re.findall(r'V2-\d+', pypdf2_text)
        print(f"  V2- matches: {v2_matches}")
    
    print("PDFMiner V2- search:")
    print(f"  V2- found: {'V2-' in pdfminer_text}")
    if 'V2-' in pdfminer_text:
        import re
        v2_matches = re.findall(r'V2-\d+', pdfminer_text)
        print(f"  V2- matches: {v2_matches}")
    
    # Parse results
    pypdf2_result = parse_invoice_text(pypdf2_text, debug=False)
    pdfminer_result = parse_invoice_text(pdfminer_text, debug=False)
    
    print(f"PyPDF2 numero: {repr(pypdf2_result.get('documento', {}).get('numero'))}")
    print(f"PDFMiner numero: {repr(pdfminer_result.get('documento', {}).get('numero'))}")

if __name__ == "__main__":
    # Test a specific V2- file
    test_file = "2025-08-12 Fattura 250039161 PROGEO SCA.pdf"
    if os.path.exists(test_file):
        test_v2_extraction(test_file)
    else:
        print(f"File not found: {test_file}")
        # Try another V2- file
        test_file = "2025-07-30 Fattura V2-250036527 PROGEO SCA.pdf"
        if os.path.exists(test_file):
            test_v2_extraction(test_file)
        else:
            print(f"File not found: {test_file}")