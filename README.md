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

When using the example `config.imap.json`, IMAP credentials are read from the
environment. Define `IMAP_EMAIL_01` and `IMAP_PASSWORD_01` before running the
application:

```bash
export IMAP_EMAIL_01="nomecasella@nomedominio.it"
export IMAP_PASSWORD_01="la password legata alla casella"
```

## Email polling triggers

Two built-in triggers allow fetching messages from email servers:

* `gmail_poll` &ndash; uses the Gmail API with an OAuth2 token. Provide a
  `token_file` path in the trigger configuration and optionally a search
  `query`. You may also specify `max_results` to limit the number of
  messages returned. To monitor multiple mailboxes in one workflow use an
  `accounts` list where each entry contains its own `token_file` and `query`.
* `imap_poll` &ndash; connects to any IMAP server using username and password.
  Required options are `host`, `username` and `password`. Optional keys are
  `port` (defaults to `993`), `mailbox` (defaults to `INBOX`), `search`
  (defaults to `UNSEEN`), `max_results` to limit how many messages are
  fetched (defaults to `100`) and `has_attachment` to filter messages by
  attachment presence (`true` keeps only messages with attachments,
  `false` keeps only those without).

## Archive and spreadsheet actions

Two archive actions download an email and its attachments then return metadata
that can be appended to a spreadsheet:

* `gmail_archive` &ndash; stores a Gmail message and/or its attachments in a
  subfolder on Google Drive or under a local directory. Provide a `token_file`
  along with either `drive_folder_id` or `local_dir`. Optional parameters let
  you skip saving the message body with `save_message` (defaults to `true`),
  skip saving attachments with `save_attachments` (defaults to `true`),
  filter attachments by extension using `attachment_types` (e.g. `[".pdf"]`),
  download file links found in the message body with `download_links`. Links are
  detected in both plain text and HTML `href` attributes and file names are
  derived from `Content-Disposition` headers when needed, and
  automatically fetch text parts delivered via `attachmentId`. Quoted replies
  are stripped from the saved message. When attachments are stored locally the
  action also returns `attachment_paths` with their full paths.
* `imap_archive` &ndash; similar functionality for standard IMAP servers. It
  requires `host`, `username` and `password` and the same destination options as
  `gmail_archive`. An optional `port` (defaults to `993`) can be provided.

The resulting metadata dictionary can be passed to `sheets_append` or the new
`excel_append` action which writes rows to a local `.xlsx` or `.xlsm` workbook.
`excel_append` formats the `datetime` field as `DD/MM/YYYY HH:MM:SS`, joins
attachment lists with a semicolon and supports a `max_message_length`
parameter to truncate the message text. It now also accepts a `records` key
containing a list of dictionaries with the same fields configured in
`fields` allowing multiple rows to be appended in a single call.

## Logging

Runtime logs are written to `pyzap.log`. Use the `--log-level` option of
`pyzap run` to change verbosity (e.g. `DEBUG` for very detailed output).
Passing `--step` pauses execution after every workflow step so you can inspect
the log before continuing. This is useful when troubleshooting new workflows.
`--iterations` limits how many cycles are executed (with `0` meaning run
forever) and `--repeat-interval` adjusts the delay between cycles in seconds
when repeating.

## Generating a Gmail API token

Several plugins use Google APIs. You need an OAuth token generated from a
`credentials.json` file created in the
[Google Cloud console](https://console.cloud.google.com/).
Enable both the **Gmail API** and the **Drive API** for your project and create a
**Desktop application** OAuth client. Download the resulting `credentials.json`
and follow these steps:

1. Place `credentials.json` in the repository root.
2. Run the helper script to start the OAuth flow:

   ```bash
   python get_gmail_token.py
   ```

3. A browser window will prompt you to log in and grant access. When finished,
   a `token.json` file is created.
4. Move `token.json` next to your `config.json` file (or reference it with the
   `token_file` option) so PyZap can authenticate.

### Scopes used

`get_gmail_token.py` requests the following scopes by default:

* `https://www.googleapis.com/auth/drive.metadata.readonly` – needed for basic
  Drive listing operations.
* `https://www.googleapis.com/auth/gmail.readonly` – allows reading messages for
  the polling and archive actions.

To use the `gmail_archive` action you must also include
`https://www.googleapis.com/auth/drive.file` which grants read/write access to
files that PyZap uploads to your Drive. Edit the `SCOPES` list in
`get_gmail_token.py` if additional permissions are required. See Google's
[OAuth 2.0 scopes documentation](https://developers.google.com/identity/protocols/oauth2/scopes)
for reference.

