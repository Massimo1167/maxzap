# PyZap Documentation

Welcome to the PyZap documentation. PyZap is a lightweight workflow automation engine inspired by Zapier. This page shows how to get the project running and configure simple workflows.

## Installation

1. Create a Python 3 virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate
   ```
2. Install the required libraries:
   ```bash
   pip install -r requirements.txt
   ```

## Obtaining API credentials

Some triggers and actions require API credentials. The Gmail polling trigger uses OAuth2 tokens stored in `token.json`. To generate this token download a `credentials.json` file for a **Desktop application** from your Google Cloud project and run:

```bash
python get_gmail_token.py
```

Follow the browser flow and place the generated `token.json` next to your `config.json` file (or reference it with the `token_file` option).

The Gmail trigger also accepts a `max_results` option to control how many
messages are fetched on each poll.
You can monitor multiple Gmail accounts in one workflow by providing an
`accounts` list containing per-account `token_file` and `query` values.

Other actions like Google Drive uploads or Sheets updates expect a bearer token in the `GDRIVE_TOKEN` environment variable. Slack notifications simply need a webhook URL.

## Running the engine

Use the CLI to start the workflow engine:

```bash
python -m pyzap.cli run config.json
```

The log file `pyzap.log` records activity. Pass `--step` to pause between steps for debugging.

## Example configuration

Workflow definitions live in `config.json`. Below is a trimmed example showing a Gmail polling trigger followed by three actions:

```json
{
  "admin_email": "admin@example.com",
  "smtp": {"host": "localhost", "port": 25},
  "workflows": [
    {
      "id": "example-zap",
      "trigger": {
        "type": "gmail_poll",
        "query": "label:inbox",
        "max_results": 10
      },
      "actions": [
        {"type": "g_drive_upload", "params": {"folder_id": "FOLDER_ID"}},
        {"type": "sheets_append", "params": {"sheet_id": "SHEET_ID", "range": "Sheet1!A:B"}},
        {"type": "slack_notify", "params": {"webhook_url": "https://hooks.slack.com/..."}}
      ]
    }
  ]
}
```

Values may also reference environment variables using the `${VAR_NAME}` syntax as seen in the provided `config.json` file.

Keys beginning with an underscore, for example `_comment`, are ignored when the
configuration is loaded. This lets you annotate the JSON file with inline
comments.

With the configuration in place simply run `pyzap` as shown above and watch your automations execute.

## Archiving email

Two archive actions can store a message and attachments then feed the resulting
metadata into spreadsheet appenders:

```json
{
  "id": "archive-example",
  "trigger": {"type": "gmail_poll"},
  "actions": [
    {
      "type": "gmail_archive",
      "params": {
        "local_dir": "./archive",
        "attachment_types": [".pdf"],
        "save_message": false,
        "save_attachments": false,
        "download_links": true
      }
    },
    {"type": "excel_append", "params": {"file": "log.xlsx"}}
  ]
}
```

The same concept works with `imap_archive` in place of `gmail_archive` and the
`sheets_append` action for Google Sheets.
