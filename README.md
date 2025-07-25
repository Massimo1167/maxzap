# PyZap

PyZap is a monolithic workflow automation tool inspired by Zapier. This repository
contains a minimal skeleton implementing plugin-based triggers and actions,
a command line interface, and a small Flask web dashboard.

```
pyzap/
  core.py          - workflow engine and main loop
  cli.py           - command line interface
  webapp.py        - minimal Flask dashboard
  formatter.py     - data transformation utilities
  plugins/         - trigger and action implementations

config.json.example - example workflow configuration
tests/              - pytest scaffolding
docs/               - MkDocs documentation skeleton
```

This code base is a starting point only. Business logic for each plugin must be
implemented along with authentication credentials for external services.

## Installation

Install the project dependencies using `pip`:

```bash
pip install -r requirements.txt
```

## Running Tests

Run the test suite with `pytest` to verify everything works as expected:

```bash
pytest -vv
```

The `-vv` flag shows each test result clearly.

## Configuration

The main configuration file now supports global settings in addition to the
workflow list. Administrators can provide an `admin_email` address along with
SMTP credentials used for failure notifications:

```json
{
  "admin_email": "admin@example.com",
  "smtp": {
    "host": "localhost",
    "port": 25,
    "username": "",
    "password": ""
  },
  "workflows": [ ... ]
}
```

## Email polling triggers

Two built-in triggers allow fetching messages from email servers:

* `gmail_poll` &ndash; uses the Gmail API with an OAuth2 token. Provide a
  `token_file` path in the trigger configuration and optionally a search
  `query`.
* `imap_poll` &ndash; connects to any IMAP server using username and password.
  Required options are `host`, `username` and `password`. Optional keys are
  `mailbox` (defaults to `INBOX`) and `search` (defaults to `UNSEEN`).

## Logging

Runtime logs are written to `pyzap.log`. Use the `--log-level` option of
`pyzap run` to change verbosity (e.g. `DEBUG` for very detailed output).
Passing `--step` pauses execution after every workflow step so you can inspect
the log before continuing. This is useful when troubleshooting new workflows.

## Generating a Gmail API token

The `gmail_poll` trigger requires an OAuth token file created from Google API credentials. Download `credentials.json` for a *Desktop app* from the Google Cloud console with Gmail and Drive APIs enabled. Then run:

```bash
python get_gmail_token.py
```

Your browser will open to authorize access. When the flow completes a `token.json` file is created. Place this file next to `config.json` (or specify its path via the `token_file` setting) so PyZap can authenticate.

### Scopes used

The default token requests the following OAuth scopes:

* https://www.googleapis.com/auth/drive.metadata.readonly
* https://www.googleapis.com/auth/gmail.readonly

Adjust `get_gmail_token.py` if your workflows need additional scopes.

