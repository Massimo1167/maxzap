#!/usr/bin/env python3

# Test script per confrontare estrazione testo
import sys
sys.path.append('.')

from pdf_utils_ocr import _extract_text_pdf_native

def main():
    pdf_path = "2025-08-12 Fattura V2-250039161 PROGEO SCA.pdf"
    
    print("=== ESTRAZIONE TESTO NATIVO ===")
    txt = _extract_text_pdf_native(pdf_path)
    print(f"Lunghezza testo: {len(txt)} caratteri")
    print("=== PRIME 50 RIGHE ===")
    
    lines = txt.replace("\r", "").split("\n")
    for i, line in enumerate(lines[:50]):
        print(f"[{i:2d}]: {repr(line)}")
    
    print("\n=== RIGHE SPECIFICHE ATTORNO ALL'HEADER ===")
    for i, line in enumerate(lines):
        if "Tipologia documento" in line or "Art. 73" in line:
            start = max(0, i-2)
            end = min(len(lines), i+10)
            print(f"Found 'Tipologia documento' or 'Art. 73' at line {i}")
            for j in range(start, end):
                marker = " --> " if j == i else "     "
                print(f"{marker}[{j:2d}]: {repr(lines[j])}")
            break

if __name__ == "__main__":
    main()