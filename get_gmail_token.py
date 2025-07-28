from __future__ import print_function
import os.path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

# SCOPES: modifica se serve un ambito diverso
SCOPES = [
    'https://www.googleapis.com/auth/drive.metadata.readonly',
    'https://www.googleapis.com/auth/drive.file',
    'https://www.googleapis.com/auth/gmail.readonly'
]

def main():
    creds = None
    # Se token.json esiste, caricalo
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    # Se le credenziali non sono valide o mancanti, avvia il flow
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                'credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        # Salva il token per usi futuri
        with open('token.json', 'w') as token:
            token.write(creds.to_json())
    print("✔️ token.json creato con successo")

if __name__ == '__main__':
    main()
