#!/usr/bin/env python3
"""
Test parse function with debug enabled
"""

import os
from PyPDF2 import PdfReader
from pyzap.pdf_invoice import parse_invoice_text

def test_parse_with_debug(pdf_path):
    print(f"=== Testing parse with debug for {pdf_path} ===")
    
    # PyPDF2 extraction
    with open(pdf_path, 'rb') as f:
        reader = PdfReader(f)
        pypdf2_text = ''
        for page in reader.pages:
            pypdf2_text += page.extract_text() or ''
    
    print("Parsing with debug enabled...")
    result = parse_invoice_text(pypdf2_text, debug=True)
    print(f"Final numero result: {repr(result.get('documento', {}).get('numero'))}")

if __name__ == "__main__":
    test_file = "2025-08-12 Fattura 250039161 PROGEO SCA.pdf"
    if os.path.exists(test_file):
        test_parse_with_debug(test_file)
    else:
        print(f"File not found: {test_file}")