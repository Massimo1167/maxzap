# Plugin Progeo Delivery Note Parser

## Descrizione

Il plugin `progeo_delivery_note` è un'action PyZap che permette di estrarre automaticamente informazioni strutturate dalle delivery note (bolle di consegna) in formato PDF della ditta Progeo SCA.

## Caratteristiche

- ✅ Estrazione automatica di informazioni documento (numero, data, tipo)
- ✅ Parsing dati mittente (Progeo) e destinatario
- ✅ Estrazione informazioni trasporto (vettore, colli, peso)
- ✅ Lista articoli con codici, descrizioni e quantità
- ✅ Note e causale trasporto
- ✅ Supporto fallback OCR per PDF non standard
- ✅ Output in formato JSON strutturato
- ✅ Modalità debug per troubleshooting

## Installazione

Il plugin è già incluso in PyZap. Assicurati di avere le dipendenze necessarie:

```bash
pip install pdfminer.six pdf2image pytesseract
```

Per l'OCR, installa anche Tesseract:
- Windows: Scarica da https://github.com/UB-Mannheim/tesseract/wiki
- Linux: `sudo apt install tesseract-ocr tesseract-ocr-ita`
- macOS: `brew install tesseract`

## Parametri

| Parametro | Tipo | Richiesto | Descrizione |
|-----------|------|-----------|-------------|
| `pdf_path` | str | ✅ | Percorso al file PDF della delivery note |
| `output_dir` | str | ❌ | Directory per salvare i risultati JSON (default: `./output`) |
| `debug` | bool | ❌ | Abilita output di debug (default: `false`) |

## Formato Output

```json
{
  "documento": {
    "tipo": "Delivery Note",
    "numero": "DDT-250039161",
    "data": "12-08-2025",
    "data_consegna": "13-08-2025"
  },
  "mittente": {
    "denominazione": "PROGEO SCA",
    "p_iva": "IT00127250355",
    "indirizzo": "Via Asseverati, 1",
    "citta": "Reggio Emilia",
    "cap": "42122",
    "provincia": "RE"
  },
  "destinatario": {
    "denominazione": "CLIENTE ESEMPIO SRL",
    "indirizzo": "Via Example, 123",
    "citta": "Milano",
    "cap": "20100",
    "provincia": "MI"
  },
  "trasporto": {
    "vettore": "Corriere Express SRL",
    "modalita": "Porto franco",
    "data_ritiro": "12-08-2025",
    "colli": 5,
    "peso": 25.5
  },
  "articoli": [
    {
      "codice": "ART001",
      "descrizione": "Prodotto Esempio",
      "quantita": 10.0,
      "unita_misura": "PZ",
      "lotto": "L20250812",
      "scadenza": "12-08-2026"
    }
  ],
  "note": {
    "note": "Consegna urgente",
    "causale_trasporto": "Vendita"
  }
}
```

## Esempi di Uso

### Configurazione Workflow

```json
{
  "workflows": [
    {
      "id": "progeo-delivery-processing",
      "trigger": {
        "type": "gmail_poll",
        "params": {
          "query": "from:progeo.it subject:delivery filename:pdf"
        }
      },
      "actions": [
        {
          "type": "progeo_delivery_note",
          "params": {
            "pdf_path": "{downloaded_file}",
            "output_dir": "./delivery_notes",
            "debug": false
          }
        }
      ]
    }
  ]
}
```

### Test Manuale

```bash
# Test di base
python test_progeo_delivery_note.py delivery_note.pdf

# Con debug abilitato
python test_progeo_delivery_note.py --debug delivery_note.pdf

# Salva risultati JSON
python test_progeo_delivery_note.py --save-json --output-dir ./results delivery_note.pdf
```

### Uso Programmatico

```python
from pyzap.plugins.progeo_delivery_note import ProgeoDeliveryNoteAction

# Crea l'action
action = ProgeoDeliveryNoteAction(
    pdf_path="delivery_note.pdf",
    output_dir="./output",
    debug=True
)

# Esegui il parsing
input_data = {}
result = action.execute(input_data)

if result['parsed_successfully']:
    delivery_note = result['delivery_note']
    print(f"DDT: {delivery_note['documento']['numero']}")
else:
    print(f"Errore: {result['error']}")
```

## Casi d'Uso

### 1. Automazione Logistica
- Monitoraggio automatico email delivery note
- Aggiornamento inventario basato su consegne
- Notifiche team logistica

### 2. Contabilità e Amministrazione  
- Registrazione automatica delivery note in Excel
- Controllo congruenza con ordini
- Archiviazione documenti digitali

### 3. Integrazione ERP
- Import automatico dati in sistemi gestionali
- Sincronizzazione con magazzino
- Report consegne

## Troubleshooting

### Estrazione Testo Fallisce
```bash
# Test con debug per vedere l'output di estrazione
python test_progeo_delivery_note.py --debug delivery_note.pdf
```

### Pattern Non Riconosciuti
Il plugin è ottimizzato per il formato standard Progeo. Per delivery note con layout diversi:

1. Abilita debug per vedere il testo estratto
2. Modifica i pattern regex in `_parse_*` methods
3. Aggiungi test cases specifici

### Performance OCR
Se l'estrazione nativa fallisce e usa OCR:
- Assicurati che Tesseract sia installato correttamente
- Verifica la qualità del PDF (scansioni poco leggibili)
- Considera pre-processing delle immagini

## Development

### Aggiungere Nuovi Campi

1. Modifica la struttura dati in `_parse_delivery_note()`
2. Implementa logic di parsing nel metodo appropriato
3. Aggiungi test cases in `test_progeo_delivery_note.py`
4. Aggiorna la documentazione

### Pattern Regex Personalizzati

I pattern principali si trovano nei metodi `_parse_*`. Esempi:

```python
# Numero documento
numero_match = re.search(r'(?:DDT|Delivery).*?(\w{2,4}[-/]?\d{6,})', text, re.IGNORECASE)

# Data
date_match = re.search(r'\b(\d{2}[-/]\d{2}[-/]\d{4})\b', text)

# Articoli  
article_match = re.match(r'(\w+)\s+(.+?)\s+([\d,\.]+)\s+(\w+)', line)
```

## Versioni e Changelog

### v1.0.0 (Current)
- Implementazione iniziale
- Supporto base delivery note Progeo
- Estrazione campi principali
- Test suite completa

### Roadmap
- [ ] Supporto multi-page delivery notes
- [ ] Riconoscimento automatico layout variants
- [ ] Integrazione AI/ML per parsing avanzato
- [ ] Supporto altri formati (Excel, XML)