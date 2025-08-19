#!/usr/bin/env python3
"""
Plugin per parsing delivery note Progeo SCA in formato PDF.

Questo plugin estende BaseAction per processare delivery note (bolla di consegna)
della ditta Progeo SCA e estrarre informazioni strutturate.
"""

import os
import re
from typing import Any, Dict, List, Optional
from ..core import BaseAction
from ..pdf_invoice import _extract_text_pdf_native, _extract_text_pdf_ocr, _norm_ws


class ProgeoDeliveryNoteAction(BaseAction):
    """
    Action per parsing delivery note Progeo SCA.
    
    Parametri:
        pdf_path (str): Percorso al file PDF della delivery note
        output_dir (str): Directory di output per i file estratti
        debug (bool): Abilita output di debug
    """
    
    def __init__(self, params: Dict[str, Any]):
        # Inizializza BaseAction con tutti i parametri
        super().__init__(params)
        
        # Estrai parametri specifici del plugin
        self.pdf_path = params.get('pdf_path')
        self.output_dir = params.get('output_dir', './output')
        self.debug = params.get('debug', False)
        
        if not self.pdf_path:
            raise ValueError("Parametro 'pdf_path' richiesto")
    
    def execute(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Esegue il parsing della delivery note Progeo.
        
        Args:
            data: Dati di input dal trigger
            
        Returns:
            Dict contenente i dati estratti e normalizzati per excel_append
        """
        try:
            # Estrai testo dal PDF
            text = self._extract_pdf_text()
            
            if not text:
                raise ValueError(f"Impossibile estrarre testo da {self.pdf_path}")
            
            # Parse della delivery note
            parsed_data = self._parse_delivery_note(text)
            
            # Salva risultati se richiesto
            if self.output_dir:
                self._save_results(parsed_data)
            
            # Crea il risultato compatibile con excel_append (come split_invoice_pdf)
            result_data = data.copy()
            
            # Dati principali per excel_append
            documento = parsed_data.get('documento', {})
            mittente = parsed_data.get('mittente', {})
            destinatario = parsed_data.get('destinatario', {})
            trasporto = parsed_data.get('trasporto', {})
            note_info = parsed_data.get('note', {})
            articoli = parsed_data.get('articoli', [])
            
            # Aggiorna con dati normalizzati per excel_append
            result_data.update({
                # Campi compatibili con excel_append
                'documento_tipo': documento.get('tipo', ''),
                'documento_numero': documento.get('numero', ''),
                'documento_data': documento.get('data', ''),
                'documento_pagina': documento.get('pagina', ''),
                
                'mittente_denominazione': mittente.get('denominazione', ''),
                'mittente_piva': mittente.get('p_iva', ''),
                'mittente_indirizzo': mittente.get('indirizzo', ''),
                'mittente_citta': mittente.get('citta', ''),
                'mittente_cap': mittente.get('cap', ''),
                'mittente_provincia': mittente.get('provincia', ''),
                
                'destinatario_denominazione': destinatario.get('denominazione', ''),
                'destinatario_piva': destinatario.get('p_iva', ''),
                'destinatario_codice_fiscale': destinatario.get('codice_fiscale', ''),
                'destinatario_codice_cliente': destinatario.get('codice_cliente', ''),
                'destinatario_indirizzo': destinatario.get('indirizzo', ''),
                'destinatario_citta': destinatario.get('citta', ''),
                'destinatario_cap': destinatario.get('cap', ''),
                'destinatario_provincia': destinatario.get('provincia', ''),
                
                'trasporto_vettore': trasporto.get('vettore', ''),
                'trasporto_data_ritiro': trasporto.get('data_ritiro', ''),
                'trasporto_ora_ritiro': trasporto.get('ora_ritiro', ''),
                'trasporto_peso_netto_kg': trasporto.get('peso_netto_kg', ''),
                'trasporto_tipo': trasporto.get('tipo_trasporto', ''),
                'trasporto_aspetto_esteriore': trasporto.get('aspetto_esteriore', ''),
                
                'numero_ordine': note_info.get('numero_ordine', ''),
                'riferimento_ordine_cliente': note_info.get('riferimento_ordine_cliente', ''),
                'riferimento_carico': note_info.get('riferimento_carico', ''),
                'metodo_pagamento': note_info.get('metodo_pagamento', ''),
                'causale': note_info.get('causale', ''),
                
                'numero_articoli': len(articoli),
                'articoli_descrizione': ' | '.join([art.get('descrizione', '')[:50] for art in articoli[:3]]),  # Prime 3 descrizioni accorciate
                'peso_totale_articoli': sum([art.get('quantita', 0) for art in articoli]),
                
                # Campi per debugging/integrazione
                'delivery_note_raw': parsed_data,  # Dati completi per debug
                'pdf_file_path': self.pdf_path,
                'parsed_successfully': True,
                'parser_version': '1.0.0',
            })
            
            if self.debug:
                print(f"DEBUG: Delivery note parsed successfully: {documento.get('numero')}")
                print(f"DEBUG: Found {len(articoli)} articles")
                print(f"DEBUG: Destinatario: {destinatario.get('denominazione', 'N/A')}")
            
            return result_data
            
        except Exception as e:
            error_msg = f"Errore nel parsing delivery note {self.pdf_path}: {str(e)}"
            if self.debug:
                print(f"DEBUG: {error_msg}")
            
            result_data = data.copy()
            result_data.update({
                'delivery_note_raw': None,
                'pdf_file_path': self.pdf_path,
                'parsed_successfully': False,
                'error': error_msg,
                'parser_version': '1.0.0',
            })
            return result_data
    
    def _extract_pdf_text(self) -> str:
        """Estrae testo dal PDF usando le funzioni ottimizzate."""
        if self.debug:
            print(f"DEBUG: Extracting text from {self.pdf_path}")
        
        # Prova prima estrazione nativa
        text = _extract_text_pdf_native(self.pdf_path, debug=self.debug)
        
        # Se fallisce, prova OCR
        if not text or len(text.strip()) < 50:
            if self.debug:
                print("DEBUG: Native extraction failed, trying OCR")
            text = _extract_text_pdf_ocr(self.pdf_path, debug=self.debug)
        
        return text
    
    def _parse_delivery_note(self, text: str) -> Dict[str, Any]:
        """
        Parse principale della delivery note Progeo.
        
        Args:
            text: Testo estratto dal PDF
            
        Returns:
            Dict con i dati strutturati della delivery note
        """
        if self.debug:
            print(f"DEBUG: Parsing delivery note text ({len(text)} chars)")
        
        # Normalizza il testo
        clean_text = "\n".join(_norm_ws(ln) for ln in text.replace("\r", "").splitlines())
        lines = [ln for ln in clean_text.split("\n") if ln.strip()]
        
        data = {
            "documento": self._parse_document_info(clean_text, lines),
            "mittente": self._parse_mittente(clean_text, lines),
            "destinatario": self._parse_destinatario(clean_text, lines),
            "trasporto": self._parse_trasporto(clean_text, lines),
            "articoli": self._parse_articoli(clean_text, lines),
            "note": self._parse_note(clean_text, lines),
        }
        
        return data
    
    def _parse_document_info(self, text: str, lines: List[str]) -> Dict[str, Any]:
        """Estrae informazioni del documento basato sul formato reale Progeo."""
        info = {}
        
        # Numero bolla - pattern Progeo BB25-XXXXXX
        numero_match = re.search(r'BB\d{2}-\d{6}', text)
        if numero_match:
            info['numero'] = numero_match.group(0)
        
        # Data documento - cerca dopo "Data"
        for i, line in enumerate(lines):
            if line.strip() == 'Data' and i + 1 < len(lines):
                date_line = lines[i + 1].strip()
                # Formato DD/MM/YY
                if re.match(r'\d{2}/\d{2}/\d{2}', date_line):
                    info['data'] = date_line
                break
        
        # Tipo documento - sempre DDT per le bolle Progeo
        if 'DDT' in text:
            info['tipo'] = 'DDT - Documento di Trasporto'
        
        # Pagina
        page_match = re.search(r'Pagina\s+(\d+/\d+)', text)
        if page_match:
            info['pagina'] = page_match.group(1)
        
        if self.debug:
            print(f"DEBUG: Document info parsed: {info}")
        
        return info
    
    def _parse_mittente(self, text: str, lines: List[str]) -> Dict[str, Any]:
        """Estrae informazioni del mittente (Progeo) dalla bolla reale."""
        mittente = {}
        
        # Progeo è sempre il mittente - info standard
        mittente['denominazione'] = 'PROGEO SCA'
        
        # Cerca "Luogo Ritiro Merce" che è l'indirizzo Progeo
        for i, line in enumerate(lines):
            if 'Luogo Ritiro Merce' in line and i + 1 < len(lines):
                indirizzo_line = lines[i + 1]
                # Pattern: "VIA ASSEVERATI, 1 42122 Reggio Emilia (RE)"
                addr_match = re.match(r'(.*?)\s+(\d{5})\s+(.*?)\s+\(([A-Z]{2})\)', indirizzo_line)
                if addr_match:
                    mittente['indirizzo'] = addr_match.group(1).strip()
                    mittente['cap'] = addr_match.group(2)
                    mittente['citta'] = addr_match.group(3).strip()
                    mittente['provincia'] = addr_match.group(4)
                break
        
        # P.IVA Progeo (valore standard noto)
        mittente['p_iva'] = 'IT00127250355'
        
        if self.debug:
            print(f"DEBUG: Mittente parsed: {mittente}")
        
        return mittente
    
    def _parse_destinatario(self, text: str, lines: List[str]) -> Dict[str, Any]:
        """Estrae informazioni del destinatario dalla bolla reale."""
        destinatario = {}
        
        # Cerca le informazioni del cliente
        cliente_found = False
        for i, line in enumerate(lines):
            # Dopo "Cliente" troviamo la denominazione
            if line.strip() == 'Cliente' and not cliente_found:
                # Salta possibili righe intermedie e cerca la denominazione
                for j in range(i + 1, min(i + 5, len(lines))):
                    candidate = lines[j].strip()
                    # La denominazione è una riga lunga che non è un campo
                    if (len(candidate) > 10 and 
                        not candidate.isdigit() and 
                        not re.match(r'^\d{2}/\d{2}/\d{2}$', candidate) and
                        'AZIENDA' in candidate.upper()):
                        
                        denominazione_parts = [candidate]
                        # Cerca righe successive che potrebbero essere parte della denominazione
                        k = j + 1
                        while k < len(lines) and k < j + 3:
                            next_line = lines[k].strip()
                            if (len(next_line) > 5 and 
                                not next_line.startswith('VIA') and
                                not re.match(r'\d{5}', next_line) and
                                'AGRICO' in next_line.upper()):
                                denominazione_parts.append(next_line)
                                k += 1
                            else:
                                break
                        
                        destinatario['denominazione'] = ' '.join(denominazione_parts)
                        
                        # Cerca indirizzo nelle righe successive
                        for addr_idx in range(k, min(k + 3, len(lines))):
                            addr_line = lines[addr_idx].strip()
                            if addr_line.startswith('VIA'):
                                destinatario['indirizzo'] = addr_line
                                
                                # Cerca CAP e città nella riga successiva
                                if addr_idx + 1 < len(lines):
                                    cap_line = lines[addr_idx + 1].strip()
                                    cap_match = re.match(r'(\d{5})\s+(.*?)\s+\(([A-Z]{2})\)', cap_line)
                                    if cap_match:
                                        destinatario['cap'] = cap_match.group(1)
                                        destinatario['citta'] = cap_match.group(2).strip()
                                        destinatario['provincia'] = cap_match.group(3)
                                break
                        
                        cliente_found = True
                        break
                
                if cliente_found:
                    break
        
        # Cerca anche P.IVA e Codice Fiscale del cliente
        for i, line in enumerate(lines):
            if line.strip() == 'P.IVA' and i + 2 < len(lines):
                # P.IVA e C.F. sono sulla stessa riga delle etichette
                piva_line = lines[i + 2].strip()  # Salta "C.F."
                cf_line = lines[i + 3].strip() if i + 3 < len(lines) else ""
                
                if re.match(r'\d{11}', piva_line):
                    destinatario['p_iva'] = piva_line
                if re.match(r'\d{11}', cf_line):
                    destinatario['codice_fiscale'] = cf_line
                break
        
        # Cerca codice cliente
        for i, line in enumerate(lines):
            if 'Codice Cliente' in line and i + 1 < len(lines):
                destinatario['codice_cliente'] = lines[i + 1].strip()
                break
        
        if self.debug:
            print(f"DEBUG: Destinatario parsed: {destinatario}")
        
        return destinatario
    
    def _parse_trasporto(self, text: str, lines: List[str]) -> Dict[str, Any]:
        """Estrae informazioni di trasporto dalla bolla reale."""
        trasporto = {}
        
        # Peso Netto
        for i, line in enumerate(lines):
            if 'Peso Netto Kg' in line and i + 1 < len(lines):
                peso_str = lines[i + 1].strip().replace('.', '').replace(',', '.')
                try:
                    trasporto['peso_netto_kg'] = float(peso_str)
                except ValueError:
                    pass
                break
        
        # Data Ritiro
        for i, line in enumerate(lines):
            if 'Data Ritiro' in line and i + 1 < len(lines):
                ritiro_line = lines[i + 1].strip()
                # Pattern: "03/01/25 09:34"
                ritiro_match = re.match(r'(\d{2}/\d{2}/\d{2})\s+(\d{2}:\d{2})', ritiro_line)
                if ritiro_match:
                    trasporto['data_ritiro'] = ritiro_match.group(1)
                    trasporto['ora_ritiro'] = ritiro_match.group(2)
                break
        
        # Vettore - può essere su più righe
        vettore_lines = []
        vettore_found = False
        for i, line in enumerate(lines):
            if not vettore_found and ('MOVITRANS' in line or 'SOCIETA\' COOPERATIVA' in line):
                vettore_found = True
                vettore_lines.append(line.strip())
                
                # Cerca righe successive con informazioni vettore
                for j in range(i + 1, min(i + 4, len(lines))):
                    next_line = lines[j].strip()
                    # Se contiene via, CAP, o partita IVA è parte del vettore
                    if (next_line.startswith('VIA') or 
                        re.search(r'\d{5}', next_line) or
                        re.search(r'\d{11}', next_line)):
                        vettore_lines.append(next_line)
                    elif ('CANOVI' in next_line or 'FE' in next_line):
                        vettore_lines.append(next_line)
                    else:
                        break
                break
        
        if vettore_lines:
            trasporto['vettore'] = ' | '.join(vettore_lines)
        
        # Tipo trasporto
        for i, line in enumerate(lines):
            if 'Vettore F.co Arrivo' in line and i + 1 < len(lines):
                trasporto['tipo_trasporto'] = lines[i + 1].strip()
                break
        
        # Aspetto esteriore
        for i, line in enumerate(lines):
            if 'Aspetto Esteriore dei Beni' in line and i + 1 < len(lines):
                trasporto['aspetto_esteriore'] = lines[i + 1].strip()
                break
        
        # Trasporto a cura
        for i, line in enumerate(lines):
            if 'Trasporto a Cura' in line and i + 1 < len(lines):
                trasporto['trasporto_a_cura'] = lines[i + 1].strip()
                break
        
        if self.debug:
            print(f"DEBUG: Trasporto parsed: {trasporto}")
        
        return trasporto
    
    def _parse_articoli(self, text: str, lines: List[str]) -> List[Dict[str, Any]]:
        """Estrae lista articoli dalla bolla reale Progeo."""
        articoli = []
        
        # Trova inizio sezione articoli (dopo "Codice" e "Descrizione")
        articles_start = None
        for i, line in enumerate(lines):
            if 'Codice' in line and i + 1 < len(lines) and 'Descrizione' in lines[i + 1]:
                articles_start = i + 2  # Salta le intestazioni
                break
        
        if articles_start is None:
            if self.debug:
                print("DEBUG: Articles section not found")
            return articoli
        
        # Trova sezione quantità per mappare le quantità agli articoli
        qty_section = {}
        qty_start = None
        for i, line in enumerate(lines):
            if 'Qta U. M.' in line:
                qty_start = i + 1
                break
        
        if qty_start:
            qty_idx = 0
            for i in range(qty_start, len(lines)):
                line = lines[i].strip()
                # Pattern quantità: "2,980 TN"
                qty_match = re.match(r'^([\d,.]+)\s+([A-Z]+)', line)
                if qty_match:
                    qty_section[qty_idx] = {
                        'quantita': float(qty_match.group(1).replace(',', '.')),
                        'unita_misura': qty_match.group(2)
                    }
                    qty_idx += 1
                elif re.search(r'PER I MANGIMI', line):
                    break
        
        # Parsing articoli
        i = articles_start
        article_idx = 0
        
        while i < len(lines):
            line = lines[i].strip()
            
            # Stop se arriviamo alla sezione quantità
            if 'Qta U. M.' in line or 'PER I MANGIMI' in line:
                break
            
            # Pattern: categoria (numero) seguito da codice
            if re.match(r'^\d{1,2}$', line):  # Categoria
                categoria = line
                
                if i + 1 < len(lines):
                    codice = lines[i + 1].strip()
                    descrizione_parts = []
                    j = i + 2
                    
                    # Raccogli righe descrizione fino al lotto
                    while j < len(lines) and not lines[j].startswith('Lotto:'):
                        candidate = lines[j].strip()
                        if (candidate and 
                            not re.match(r'^\d{1,2}$', candidate) and  # Non è una nuova categoria
                            not candidate.startswith('Qta U. M.')):  # Non è sezione quantità
                            descrizione_parts.append(candidate)
                        else:
                            break
                        j += 1
                    
                    # Cerca lotto e quantità dalla riga
                    lotto_info = ""
                    quantita_inline = None
                    if j < len(lines) and lines[j].startswith('Lotto:'):
                        lotto_line = lines[j]
                        lotto_match = re.search(r'Lotto:([^\s]+)', lotto_line)
                        qty_match = re.search(r'Qtà?:\s*([\d,.]+)', lotto_line)
                        
                        if lotto_match:
                            lotto_info = lotto_match.group(1)
                        if qty_match:
                            quantita_inline = float(qty_match.group(1).replace(',', '.'))
                    
                    # Crea articolo
                    articolo = {
                        'categoria': categoria,
                        'codice': codice,
                        'descrizione': ' | '.join(descrizione_parts),
                        'lotto': lotto_info
                    }
                    
                    # Aggiungi quantità (preferisci inline, poi da sezione separata)
                    if quantita_inline is not None:
                        articolo['quantita'] = quantita_inline
                        articolo['unita_misura'] = 'TN'  # Default per mangimi
                    elif article_idx in qty_section:
                        articolo.update(qty_section[article_idx])
                    
                    articoli.append(articolo)
                    article_idx += 1
                    
                    i = j + 1
                else:
                    i += 1
            else:
                i += 1
        
        if self.debug:
            print(f"DEBUG: Found {len(articoli)} articles")
            for idx, art in enumerate(articoli):
                print(f"DEBUG Article {idx + 1}: {art['codice']} - {art.get('quantita', 'N/A')}")
        
        return articoli
    
    def _parse_note(self, text: str, lines: List[str]) -> Dict[str, str]:
        """Estrae note e informazioni aggiuntive dalla bolla."""
        note_data = {}
        
        # Causale
        for i, line in enumerate(lines):
            if 'Causale' in line and i + 1 < len(lines):
                note_data['causale'] = lines[i + 1].strip()
                break
        
        # Note per vettore
        for i, line in enumerate(lines):
            if 'Note Per Vettore' in line:
                # Può essere seguita da più righe di note
                note_lines = []
                for j in range(i + 1, min(i + 5, len(lines))):
                    if j < len(lines) and lines[j].strip():
                        candidate = lines[j].strip()
                        if not candidate.startswith('Timbro') and len(candidate) > 5:
                            note_lines.append(candidate)
                        else:
                            break
                if note_lines:
                    note_data['note_vettore'] = ' '.join(note_lines)
                break
        
        # Condizioni di vendita
        condizioni_lines = []
        for i, line in enumerate(lines):
            if 'CONDIZIONI DI VENDITA' in line:
                condizioni_lines.append(line.strip())
                # Cerca righe successive
                for j in range(i + 1, min(i + 3, len(lines))):
                    if j < len(lines) and lines[j].strip():
                        candidate = lines[j].strip()
                        if 'accettano reclami' in candidate or 'SOTTOSCRITTO' in candidate:
                            condizioni_lines.append(candidate)
                break
        
        if condizioni_lines:
            note_data['condizioni_vendita'] = ' '.join(condizioni_lines)
        
        # Numero ordine e riferimenti
        for i, line in enumerate(lines):
            if 'Numero Ordine' in line and i + 1 < len(lines):
                note_data['numero_ordine'] = lines[i + 1].strip()
            elif 'Riferimento Ordine Cliente' in line and i + 1 < len(lines):
                note_data['riferimento_ordine_cliente'] = lines[i + 1].strip()
            elif 'Rif. Nostro Carico' in line and i + 1 < len(lines):
                note_data['riferimento_carico'] = lines[i + 1].strip()
        
        # Metodo pagamento
        for i, line in enumerate(lines):
            if 'Metodo e Condizione di Pagamento' in line and i + 1 < len(lines):
                note_data['metodo_pagamento'] = lines[i + 1].strip()
                break
        
        if self.debug:
            print(f"DEBUG: Note parsed: {note_data}")
        
        return note_data
    
    def _save_results(self, data: Dict[str, Any]) -> None:
        """Salva i risultati parsed in file JSON."""
        import json
        
        os.makedirs(self.output_dir, exist_ok=True)
        
        # Nome file basato sul numero documento
        doc_numero = data.get('documento', {}).get('numero', 'unknown')
        filename = f"progeo_delivery_note_{doc_numero}_{data.get('documento', {}).get('data', '')}.json"
        filename = re.sub(r'[^\w\-_.]', '_', filename)  # Sanitize filename
        
        filepath = os.path.join(self.output_dir, filename)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        if self.debug:
            print(f"DEBUG: Results saved to {filepath}")