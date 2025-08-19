#!/usr/bin/env python3
"""
Test per il plugin ProgeoDeliveryNoteAction.
"""

import unittest
import os
import tempfile
import json
from unittest.mock import patch, mock_open
from pyzap.plugins.progeo_delivery_note import ProgeoDeliveryNoteAction


class TestProgeoDeliveryNoteAction(unittest.TestCase):
    
    def setUp(self):
        """Setup per ogni test."""
        self.test_dir = tempfile.mkdtemp()
        self.pdf_path = os.path.join(self.test_dir, "test_delivery_note.pdf")
        
        # Crea un file PDF fittizio
        with open(self.pdf_path, 'wb') as f:
            f.write(b"fake pdf content")
    
    def tearDown(self):
        """Cleanup dopo ogni test."""
        import shutil
        shutil.rmtree(self.test_dir)
    
    def test_init_requires_pdf_path(self):
        """Test che l'init richieda pdf_path."""
        with self.assertRaises(ValueError):
            ProgeoDeliveryNoteAction()
    
    def test_init_with_valid_params(self):
        """Test init con parametri validi."""
        action = ProgeoDeliveryNoteAction(
            pdf_path=self.pdf_path,
            output_dir=self.test_dir,
            debug=True
        )
        
        self.assertEqual(action.pdf_path, self.pdf_path)
        self.assertEqual(action.output_dir, self.test_dir)
        self.assertTrue(action.debug)
    
    @patch('pyzap.plugins.progeo_delivery_note._extract_text_pdf_native')
    def test_extract_pdf_text_native_success(self, mock_extract):
        """Test estrazione testo PDF nativa."""
        mock_extract.return_value = "Test delivery note content"
        
        action = ProgeoDeliveryNoteAction(pdf_path=self.pdf_path)
        text = action._extract_pdf_text()
        
        self.assertEqual(text, "Test delivery note content")
        mock_extract.assert_called_once()
    
    @patch('pyzap.plugins.progeo_delivery_note._extract_text_pdf_ocr')
    @patch('pyzap.plugins.progeo_delivery_note._extract_text_pdf_native')
    def test_extract_pdf_text_fallback_to_ocr(self, mock_native, mock_ocr):
        """Test fallback a OCR quando native extraction fallisce."""
        mock_native.return_value = ""  # Native extraction fails
        mock_ocr.return_value = "OCR extracted content"
        
        action = ProgeoDeliveryNoteAction(pdf_path=self.pdf_path)
        text = action._extract_pdf_text()
        
        self.assertEqual(text, "OCR extracted content")
        mock_native.assert_called_once()
        mock_ocr.assert_called_once()
    
    def test_parse_document_info(self):
        """Test parsing informazioni documento."""
        test_text = """
        DELIVERY NOTE DDT-250039161
        Data: 12-08-2025
        """
        
        action = ProgeoDeliveryNoteAction(pdf_path=self.pdf_path)
        result = action._parse_document_info(test_text, test_text.split('\n'))
        
        self.assertEqual(result['numero'], 'DDT-250039161')
        self.assertEqual(result['data'], '12-08-2025')
        self.assertEqual(result['tipo'], 'Delivery Note')
    
    def test_parse_mittente(self):
        """Test parsing informazioni mittente."""
        test_text = """
        Mittente:
        PROGEO SCA
        P.IVA: IT00127250355
        Via Asseverati, 1
        42122 Reggio Emilia RE
        """
        
        action = ProgeoDeliveryNoteAction(pdf_path=self.pdf_path)
        result = action._parse_mittente(test_text, test_text.split('\n'))
        
        self.assertEqual(result['denominazione'], 'PROGEO SCA')
        self.assertEqual(result['p_iva'], 'IT00127250355')
        self.assertEqual(result['indirizzo'], 'Via Asseverati, 1')
        self.assertEqual(result['citta'], 'Reggio Emilia')
    
    def test_parse_trasporto(self):
        """Test parsing informazioni trasporto."""
        test_text = """
        Vettore: Corriere Express SRL
        Porto franco
        N. colli: 5
        Peso: 25,5 Kg
        """
        
        action = ProgeoDeliveryNoteAction(pdf_path=self.pdf_path)
        result = action._parse_trasporto(test_text, test_text.split('\n'))
        
        self.assertEqual(result['vettore'], 'Corriere Express SRL')
        self.assertEqual(result['colli'], 5)
        self.assertEqual(result['peso'], 25.5)
    
    def test_parse_articoli(self):
        """Test parsing lista articoli."""
        test_lines = [
            "Codice Descrizione Quantità UM",
            "ABC123 Prodotto Test 10 PZ",
            "DEF456 Altro Prodotto 5,5 KG",
            "Note: Fine tabella"
        ]
        
        action = ProgeoDeliveryNoteAction(pdf_path=self.pdf_path)
        result = action._parse_articoli("", test_lines)
        
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]['codice'], 'ABC123')
        self.assertEqual(result[0]['descrizione'], 'Prodotto Test')
        self.assertEqual(result[0]['quantita'], 10.0)
        self.assertEqual(result[1]['quantita'], 5.5)
    
    @patch('pyzap.plugins.progeo_delivery_note._extract_text_pdf_native')
    def test_execute_success(self, mock_extract):
        """Test esecuzione completa con successo."""
        mock_extract.return_value = """
        DELIVERY NOTE DDT-250039161
        Data: 12-08-2025
        PROGEO SCA
        Destinatario: Test Cliente
        """
        
        action = ProgeoDeliveryNoteAction(
            pdf_path=self.pdf_path,
            output_dir=self.test_dir
        )
        
        input_data = {'test': 'data'}
        result = action.execute(input_data)
        
        self.assertTrue(result['parsed_successfully'])
        self.assertIsNotNone(result['delivery_note'])
        self.assertEqual(result['pdf_path'], self.pdf_path)
    
    @patch('pyzap.plugins.progeo_delivery_note._extract_text_pdf_native')
    def test_execute_failure(self, mock_extract):
        """Test gestione errori durante esecuzione."""
        mock_extract.side_effect = Exception("Extraction failed")
        
        action = ProgeoDeliveryNoteAction(pdf_path=self.pdf_path)
        
        input_data = {'test': 'data'}
        result = action.execute(input_data)
        
        self.assertFalse(result['parsed_successfully'])
        self.assertIsNone(result['delivery_note'])
        self.assertIn('error', result)
    
    @patch('builtins.open', new_callable=mock_open)
    @patch('os.makedirs')
    def test_save_results(self, mock_makedirs, mock_file):
        """Test salvataggio risultati."""
        test_data = {
            'documento': {'numero': 'DDT-123', 'data': '12-08-2025'},
            'mittente': {'denominazione': 'PROGEO SCA'}
        }
        
        action = ProgeoDeliveryNoteAction(
            pdf_path=self.pdf_path,
            output_dir=self.test_dir
        )
        
        action._save_results(test_data)
        
        mock_makedirs.assert_called_once_with(self.test_dir, exist_ok=True)
        mock_file.assert_called_once()


if __name__ == '__main__':
    unittest.main()