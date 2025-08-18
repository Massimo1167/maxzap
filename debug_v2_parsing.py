#!/usr/bin/env python3
"""
Debug V2 parsing step by step
"""

import os
import re
from PyPDF2 import PdfReader
from pdfminer.high_level import extract_text

def debug_v2_step_by_step(pdf_path):
    print(f"=== Step by step V2 debug for {pdf_path} ===")
    
    # PyPDF2 extraction
    with open(pdf_path, 'rb') as f:
        reader = PdfReader(f)
        pypdf2_text = ''
        for page in reader.pages:
            pypdf2_text += page.extract_text() or ''
    
    print("PyPDF2 V2 context analysis:")
    v2_pos = pypdf2_text.find('V2')
    if v2_pos >= 0:
        start = max(0, v2_pos - 50)
        end = min(len(pypdf2_text), v2_pos + 100)
        context = pypdf2_text[start:end]
        print(f"Context: {repr(context)}")
        
        # Simulate the parsing logic
        lines = pypdf2_text.replace("\r", "").splitlines()
        clean_text = "\n".join(line.strip() for line in lines if line.strip())
        
        # Look for documento section
        header_match = re.search(r'Tipologia\s+documento.*?(\d{2}-\d{2}-\d{4})', clean_text, re.DOTALL)
        if header_match:
            header_section = header_match.group(0)
            print(f"Header section: {repr(header_section)}")
            
            # Test V2 pattern on this section
            v2_match = re.search(r'\bV2[\s\-_/\\]*(\d{6,})', header_section)
            print(f"V2 pattern match in header: {v2_match.group(0) if v2_match else 'None'}")
            
            # Test V2 pattern on full clean text
            v2_match_full = re.search(r'\bV2[\s\-_/\\]*(\d{6,})', clean_text)
            print(f"V2 pattern match in full text: {v2_match_full.group(0) if v2_match_full else 'None'}")

if __name__ == "__main__":
    test_file = "2025-08-12 Fattura 250039161 PROGEO SCA.pdf"
    if os.path.exists(test_file):
        debug_v2_step_by_step(test_file)
    else:
        print(f"File not found: {test_file}")