#!/usr/bin/env python3
"""
Test script specifico per verificare il fix del pagamento_modalita
"""

import re
import os
from pdfminer.high_level import extract_text
from pyzap.pdf_invoice import parse_invoice_text

def test_payment_extraction(pdf_path):
    print(f"=== Testing {pdf_path} ===")
    
    # Estrai testo con pdfminer
    text = extract_text(pdf_path)
    
    # Mostra la sezione modalità pagamento
    mp_section = re.search(r'Modalit.\s*pagamento.*?MP\d{2}', text, re.DOTALL | re.IGNORECASE)
    if mp_section:
        print(f"Found payment section:\n{repr(mp_section.group(0))}")
        
        # Test manuale dei pattern
        section_text = mp_section.group(0)
        payment_types = ['RIBA', 'SEPA Direct Debit', 'SEPA', 'Bonifico', 'Domiciliazione', 'Contanti', 'RID', 'Assegno']
        for ptype in payment_types:
            if re.search(r'\b' + re.escape(ptype), section_text, re.IGNORECASE):
                print(f"Found payment type: {ptype}")
                break
        else:
            print("No payment type found in section")
    else:
        print("Payment section not found")
    
    # Test del parser completo
    result = parse_invoice_text(text)
    modalita = result.get('pagamento', {}).get('modalita')
    print(f"Parser result modalita: {repr(modalita)}")

if __name__ == "__main__":
    test_files = [
        "2025-07-30 Fattura TD01 RIVI PAOLO & C. SAS.pdf",
        "2025-07-23 Fattura 112505418437 HERA S.p.A..pdf"
    ]
    
    for filename in test_files:
        if os.path.exists(filename):
            test_payment_extraction(filename)
            print()
        else:
            print(f"File not found: {filename}")