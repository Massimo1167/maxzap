#!/usr/bin/env python3
"""
Debug V2- pattern in text
"""

import os
import re
from PyPDF2 import PdfReader
from pdfminer.high_level import extract_text

def debug_v2_pattern(pdf_path):
    print(f"=== Debugging V2- pattern in {pdf_path} ===")
    
    # PyPDF2 extraction
    with open(pdf_path, 'rb') as f:
        reader = PdfReader(f)
        pypdf2_text = ''
        for page in reader.pages:
            pypdf2_text += page.extract_text() or ''
    
    # PDFMiner extraction  
    pdfminer_text = extract_text(pdf_path)
    
    for name, text in [("PyPDF2", pypdf2_text), ("PDFMiner", pdfminer_text)]:
        print(f"\n--- {name} ---")
        
        # Find V2 context
        v2_pos = text.find('V2')
        if v2_pos >= 0:
            start = max(0, v2_pos - 30)
            end = min(len(text), v2_pos + 50)
            context = text[start:end]
            print(f"V2 context: {repr(context)}")
            
            # Try different V2 patterns
            patterns = [
                r'V2-\d+',
                r'V2.\d+',
                r'V2[^a-zA-Z]\d+',
                r'V2\W*\d+',
                r'V2[\s\-_/\\]*\d+'
            ]
            
            for pattern in patterns:
                matches = re.findall(pattern, text)
                if matches:
                    print(f"Pattern {pattern}: {matches}")
        else:
            print("V2 not found in text")

if __name__ == "__main__":
    test_file = "2025-08-12 Fattura 250039161 PROGEO SCA.pdf"
    if os.path.exists(test_file):
        debug_v2_pattern(test_file)
    else:
        # Try another V2- file
        test_file = "2025-07-30 Fattura V2-250036527 PROGEO SCA.pdf"
        if os.path.exists(test_file):
            debug_v2_pattern(test_file)
        else:
            print(f"File not found: {test_file}")