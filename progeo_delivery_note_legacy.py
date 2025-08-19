#!/usr/bin/env python3
"""
Progeo Delivery Note Legacy Parser - Versione legacy per confronto test.
Questo è un parser legacy semplificato per dimostrare il confronto.
"""

import os
import re
from typing import Any, Dict, List, Optional

# Importa direttamente le librerie per estrazione PDF
try:
    from pdfminer.high_level import extract_text
except ImportError:
    extract_text = None


class ProgeoDeliveryNoteAction:
    """
    Versione legacy del parser Progeo delivery note per confronto.
    Simula comportamento diverso per testare la funzionalità di confronto.
    """
    
    def __init__(self, params: Dict[str, Any]):
        self.pdf_path = params.get('pdf_path')
        self.output_dir = params.get('output_dir', './output')
        self.debug = params.get('debug', False)
        
        if not self.pdf_path:
            raise ValueError("Parametro 'pdf_path' richiesto")
    
    def execute(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Versione legacy - parsing semplificato con alcune differenze intenzionali.
        """
        try:
            # Parsing basico - solo estrae numero documento
            text = self._extract_pdf_text_legacy()
            
            if not text:
                raise ValueError(f"Impossibile estrarre testo da {self.pdf_path}")
            
            # Parse legacy semplificato
            parsed_data = self._parse_legacy(text)
            
            # Risultato legacy con struttura simile ma dati diversi
            result_data = data.copy()
            
            documento = parsed_data.get('documento', {})
            
            result_data.update({
                # Legacy parser ha alcuni comportamenti diversi per test
                'documento_tipo': 'Bolla di Consegna',  # Diverso dal main
                'documento_numero': documento.get('numero', ''),
                'documento_data': documento.get('data', ''),
                'documento_pagina': '',  # Legacy non estrae pagina
                
                'mittente_denominazione': 'PROGEO LEGACY',  # Diverso dal main
                'mittente_piva': 'IT00127250355',
                'mittente_indirizzo': '',  # Legacy non estrae indirizzo
                'mittente_citta': '',
                'mittente_cap': '',
                'mittente_provincia': '',
                
                'destinatario_denominazione': parsed_data.get('cliente', ''),
                'destinatario_piva': '',  # Legacy non estrae P.IVA
                'destinatario_codice_fiscale': '',
                'destinatario_codice_cliente': '',
                'destinatario_indirizzo': '',
                'destinatario_citta': '',
                'destinatario_cap': '',
                'destinatario_provincia': '',
                
                'trasporto_vettore': '',
                'trasporto_data_ritiro': '',
                'trasporto_ora_ritiro': '',
                'trasporto_peso_netto_kg': parsed_data.get('peso_kg', 0),  # Diverso formato
                'trasporto_tipo': '',
                'trasporto_aspetto_esteriore': '',
                
                'numero_ordine': '',
                'riferimento_ordine_cliente': '',
                'riferimento_carico': '',
                'metodo_pagamento': '',
                'causale': '',
                
                'numero_articoli': parsed_data.get('articoli_count', 0),
                'peso_totale_articoli': parsed_data.get('peso_totale', 0),
                'articoli_descrizione': '',
                
                'delivery_note_raw': parsed_data,
                'pdf_file_path': self.pdf_path,
                'parsed_successfully': True,
                'parser_version': 'legacy-1.0.0',
            })
            
            return result_data
            
        except Exception as e:
            error_msg = f"Legacy parser error: {str(e)}"
            result_data = data.copy()
            result_data.update({
                'delivery_note_raw': None,
                'pdf_file_path': self.pdf_path,
                'parsed_successfully': False,
                'error': error_msg,
                'parser_version': 'legacy-1.0.0',
            })
            return result_data
    
    def _extract_pdf_text_legacy(self) -> str:
        """Estrazione PDF legacy (semplificata)"""
        try:
            if extract_text:
                return extract_text(self.pdf_path)
            return ""
        except Exception:
            return ""
    
    def _parse_legacy(self, text: str) -> Dict[str, Any]:
        """
        Parsing legacy semplificato - estrae solo informazioni base.
        Simula comportamento diverso per test confronto.
        """
        data = {}
        
        # Numero documento - stesso pattern ma parsing diverso
        numero_match = re.search(r'BB\d{2}-\d{6}', text)
        if numero_match:
            numero = numero_match.group(0)
            # Legacy aggiunge prefisso per test
            data['documento'] = {
                'numero': f"LEGACY-{numero}",  # Diverso dal main
                'data': self._extract_date_legacy(text)
            }
        
        # Cliente - parsing semplificato
        if 'AZIENDA AGRICO' in text:
            data['cliente'] = 'AZIENDA AGRICOLA LEGACY'  # Diverso dal main
        elif 'PEZZUOLI' in text:
            data['cliente'] = 'PEZZUOLI LEGACY'
        
        # Peso - estrazione diversa
        peso_match = re.search(r'(\d+\.?\d*)\s*kg', text, re.IGNORECASE)
        if peso_match:
            data['peso_kg'] = float(peso_match.group(1)) * 1.1  # Legacy aggiunge 10% per test
        
        # Conteggio articoli semplificato
        articoli_count = len(re.findall(r'\d{7}', text))  # Conta codici articolo
        data['articoli_count'] = max(1, articoli_count - 1)  # Legacy sottostima per test
        
        # Peso totale calcolato diversamente
        data['peso_totale'] = data.get('peso_kg', 0) / 1000 * 0.9  # Legacy sottostima
        
        return data
    
    def _extract_date_legacy(self, text: str) -> str:
        """Estrae data con logica legacy"""
        date_match = re.search(r'\d{2}/\d{2}/\d{2}', text)
        if date_match:
            date_str = date_match.group(0)
            # Legacy cambia formato data per test
            parts = date_str.split('/')
            return f"{parts[0]}-{parts[1]}-20{parts[2]}"  # Formato diverso
        return ""