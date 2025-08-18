#!/usr/bin/env python3
"""
Analizza la struttura del testo HERA per PDFMiner
"""

import os
from pdfminer.high_level import extract_text

def analyze_hera_structure():
    pdf_path = "2025-07-23 Fattura 112505493391 HERA S.p.A..pdf"
    
    if not os.path.exists(pdf_path):
        print(f"File not found: {pdf_path}")
        return
    
    text = extract_text(pdf_path)
    
    # Find MP05 context
    mp_pos = text.find('MP05')
    if mp_pos >= 0:
        start = max(0, mp_pos - 100)
        end = min(len(text), mp_pos + 300)
        context = text[start:end]
        print(f"MP05 context:\n{repr(context)}")
        
    # Find scadenza context
    scadenza_pos = text.find('Data scadenza')
    if scadenza_pos >= 0:
        start = max(0, scadenza_pos - 100)
        end = min(len(text), scadenza_pos + 200)
        context = text[start:end]
        print(f"\nData scadenza context:\n{repr(context)}")
        
    # Find amount 9,58
    amount_pos = text.find('9,58')
    if amount_pos >= 0:
        start = max(0, amount_pos - 100)
        end = min(len(text), amount_pos + 100)
        context = text[start:end]
        print(f"\nAmount 9,58 context:\n{repr(context)}")

if __name__ == "__main__":
    analyze_hera_structure()