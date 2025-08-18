#!/usr/bin/env python3
"""
Analizza la struttura del testo di pagamento per PDFMiner
"""

import os
from pdfminer.high_level import extract_text

def analyze_payment_structure(pdf_path):
    print(f"=== Payment structure analysis for {pdf_path} ===")
    
    text = extract_text(pdf_path)
    
    # Find payment section context
    data_pos = text.find('Data scadenza')
    if data_pos >= 0:
        start = max(0, data_pos - 200)
        end = min(len(text), data_pos + 300)
        context = text[start:end]
        print(f"Payment context:\n{repr(context)}")
        
        # Look for the dates we found
        dates = ['10-09-2025']
        amounts = ['1.000,50']
        
        for date in dates:
            date_pos = text.find(date)
            if date_pos >= 0:
                start = max(0, date_pos - 100)
                end = min(len(text), date_pos + 100)
                date_context = text[start:end]
                print(f"\nDate context for {date}:\n{repr(date_context)}")
        
        for amount in amounts:
            amount_pos = text.find(amount)
            if amount_pos >= 0:
                start = max(0, amount_pos - 100)
                end = min(len(text), amount_pos + 100)
                amount_context = text[start:end]
                print(f"\nAmount context for {amount}:\n{repr(amount_context)}")

if __name__ == "__main__":
    test_file = "2025-07-31 Fattura 2632_00 EMMEDIELLE S.R.L..pdf"
    if os.path.exists(test_file):
        analyze_payment_structure(test_file)
    else:
        print(f"File not found: {test_file}")