#!/usr/bin/env python3
"""Test script per verificare il funzionamento di pdf_invoice.py dopo le modifiche"""

import sys
import os

# Aggiungi il percorso del modulo pyzap
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'pyzap'))

from pdf_invoice import parse_invoice_text

def test_pdf_parsing():
    """Test delle modifiche ai moduli pdf_invoice.py"""
    
    # Test con il file PDF di esempio
    pdf_path = r"C:/__Projects/__dev_Massimo/gmail/azienda.agricola/fatture/split/2025-07-23 Fattura None Bernardini Francesco.pdf"
    
    if not os.path.exists(pdf_path):
        print("File PDF non trovato")
        return
    
    print("Testing PDF parsing with updated logic...")
    
    # Simula l'estrazione del testo dal PDF (testo di esempio basato sui test precedenti)
    sample_text = """Cedente/prestatore (fornitore)
IVA 02018100510
Codice fiscale 02018100510
Denominazione Bernardini Francesco
Regime fiscale RF01
Indirizzo via Salaiole 151/A
Comune S.Casciano V.P.
Provincia FI
Cap 50026
Nazione IT
Telefono 3358117062

Cessionario/committente (cliente) 
IVA 01234567890
Codice fiscale 01234567890
Denominazione Az Agr Ghisolfi Roberta & Frassino
Indirizzo Via Roma 123
Comune Torino
Provincia TO
Cap 10100
Nazione IT

Tipologia documento
TD24 fattura differita di cui all'art.21, comma 4, 
terzo periodo lett.a) DPR 633/72
3097
23-07-2025
0000000

Prezzo totale
Descrizione beni/servizi  Quantita  Prezzo unitario  UM  % IVA  Prezzo totale
Olio di oliva extra vergine  1  50.00  L  0  50.00

RIEPILOGHI IVA E TOTALI
Totale imponibile 50.00
Totale imposta 0.00
Totale documento 50.00

Data scadenza 23-08-2025 50.00"""
    
    try:
        result = parse_invoice_text(sample_text)
        
        print("\nRISULTATI PARSING:")
        print("=" * 50)
        
        # Documento
        print("DOCUMENTO:")
        if 'documento' in result:
            doc = result['documento']
            print(f"   Tipologia: '{doc.get('tipo')}'")
            print(f"   Numero: '{doc.get('numero')}'")
            print(f"   Data: '{doc.get('data')}'")
            print(f"   Codice destinatario: '{doc.get('codice_destinatario')}'")
            print(f"   Art 73: {doc.get('art_73')}")
        
        # Fornitore
        print("\nFORNITORE:")
        if 'fornitore' in result:
            forn = result['fornitore']
            print(f"   Denominazione: '{forn.get('denominazione')}'")
            print(f"   P.IVA: '{forn.get('p_iva')}'")
            print(f"   CF: '{forn.get('codice_fiscale')}'")
        
        # Cliente
        print("\nCLIENTE:")
        if 'cliente' in result:
            cli = result['cliente']
            print(f"   Denominazione: '{cli.get('denominazione')}'")
            print(f"   P.IVA: '{cli.get('p_iva')}'")
            print(f"   CF: '{cli.get('codice_fiscale')}'")
        
        # Riepilogo importi
        print("\nIMPORTI:")
        if 'riepilogo_importi' in result:
            imp = result['riepilogo_importi']
            print(f"   Imponibile: {imp.get('imponibile')}")
            print(f"   Imposta: {imp.get('imposta')}")
            print(f"   Totale: {imp.get('totale')}")
        
        print("=" * 50)
        print("Test completato con successo!")
        
        # Verifica risultati attesi
        expected_tipologia = "TD24 fattura differita di cui all'art.21, comma 4, terzo periodo lett.a) DPR 633/72"
        expected_numero = "3097"
        expected_data = "23-07-2025"
        
        actual_tipologia = result.get('documento', {}).get('tipo')
        actual_numero = result.get('documento', {}).get('numero')
        actual_data = result.get('documento', {}).get('data')
        
        print("\nVERIFICA RISULTATI:")
        tipologia_match = "OK" if actual_tipologia == expected_tipologia else "ERROR"
        numero_match = "OK" if actual_numero == expected_numero else "ERROR"
        data_match = "OK" if actual_data == expected_data else "ERROR"
        
        print(f"   Tipologia: {tipologia_match} Expected: '{expected_tipologia}' | Actual: '{actual_tipologia}'")
        print(f"   Numero: {numero_match} Expected: '{expected_numero}' | Actual: '{actual_numero}'")
        print(f"   Data: {data_match} Expected: '{expected_data}' | Actual: '{actual_data}'")
        
    except Exception as e:
        print(f"Errore durante il test: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_pdf_parsing()