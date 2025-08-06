# Plugin Reference

This page lists all available triggers and actions provided by PyZap.

## Triggers

- `excel_poll` – Poll an Excel workbook for newly appended rows.
  - `file`: Path to the workbook.
  - `sheet` (optional): Worksheet name to read.
  - `state_file` (optional): File used to persist the last processed row.
  - `start_row` (optional): Starting row number, defaults to 2.
  - `filters` (optional): Mapping of column numbers to expected values.
- `excel_row_added` – Detect new rows with optional advanced filtering.
  - `file`: Path to the workbook.
  - `sheet` (optional): Worksheet name to read.
  - `state_file` (optional): File used to persist the last processed row.
  - `start_row` (optional): Starting row number, defaults to 2.
  - `filters` (optional): Mapping of column numbers to expected values or conditions.
- `excel_cell_change` – Trigger when monitored cells change value.
  - `file`: Path to the workbook.
  - `sheet` (optional): Worksheet name to read.
  - `state_file` (optional): File used to persist previous values.
  - `start_row` (optional): First row to monitor, defaults to 2.
  - `columns`: List of column numbers to watch for changes.
- `excel_file_updated` – Trigger when the Excel file modification time changes.
  - `file`: Path to the workbook.
  - `state_file` (optional): File used to store the last modification time.
- `excel_attachment_row` – Trigger on new rows where an attachment column contains data.
  - `file`: Path to the workbook.
  - `sheet` (optional): Worksheet name to read.
  - `state_file` (optional): File used to persist the last processed row.
  - `start_row` (optional): Starting row number, defaults to 2.
  - `filters` (optional): Mapping of column numbers to expected values or conditions.
  - `attachment_column`: Column number containing attachment data.
- `gmail_poll` – Poll Gmail using the Gmail API.
  - `token_file`: Path to a Gmail OAuth token JSON file.
  - `query`: Gmail search query string.
  - `max_results` (optional): Maximum number of messages to return.
  - `accounts` (optional): List of per-account configurations with the same keys.
- `imap_poll` – Poll an IMAP server for new messages.
  - `host`: IMAP server hostname.
  - `username`: Login username.
  - `password`: Login password.
  - `port` (optional): IMAP SSL port, defaults to `993`.
  - `mailbox` (optional): Mailbox to select, defaults to `INBOX`.
  - `search` (optional): IMAP search query, defaults to `UNSEEN`.
  - `max_results` (optional): Maximum number of messages to return.
  - `has_attachment` (optional): Filter messages by presence of attachments.
    Accepts `1`, `true` or `yes` to keep only messages with attachments, and `0`,
    `false` or `no` to keep only those without.
  - `mark_seen` (optional): Mark messages as read when fetching. Defaults to
    `true`; set to `false` to leave them unread using `BODY.PEEK[]`.

## Actions

- `excel_append` – Append data to an Excel workbook.
  - `file`: Path to the workbook.
  - `sheet` (optional): Worksheet name to write to.
  - `fields` (optional): Ordered list of fields to append.
  - `max_message_length` (optional): Truncate message fields to this length.
- `excel_write_row` – Create or update rows in an Excel file.
  - `file`: Path to the workbook.
  - `sheet` (optional): Worksheet name to write to.
  - `row` (optional): Row number to update; appends when omitted.
- `email_send` – Send an email using SMTP.
  - `host` (optional): SMTP server, defaults to `localhost`.
  - `port` (optional): SMTP port, defaults to 25.
  - `username` (optional): SMTP username.
  - `password` (optional): SMTP password.
  - `from_addr`: Sender email address.
  - `to_addr`: Recipient email address.
  - `subject` (optional): Email subject.
  - `body` (optional): Message body.
- `db_save` – Save data into a SQLite database.
  - `db`: Path to the SQLite database file.
  - `table` (optional): Table name, defaults to `data`.
- `file_create` – Create a file from row data.
  - `path`: Destination file path.
  - `format` (optional): Output format `txt`, `json` or `csv`.
- `attachment_download` – Download attachments referenced in a row.
  - `dest`: Directory where files are stored.
  - `rename` (optional): Filename template using row placeholders.
- `g_drive_upload` – Upload a file to Google Drive.
  - `folder_id`: Destination Drive folder ID.
  - `token` (optional): OAuth bearer token.
- `gmail_archive` – Download a Gmail message and attachments and store them.
  - `token_file`: Path to a Gmail OAuth token JSON file.
  - `drive_folder_id` (optional): Drive folder ID for storage.
  - `local_dir` (optional): Local directory for storage.
  - `token` (optional): OAuth bearer token used for Drive uploads.
  - `save_message` (optional): Save the email body, defaults to `true`.
  - `save_attachments` (optional): Download attachments, defaults to `true`.
  - `download_links` (optional): Fetch files referenced by URLs in the body.
  - `attachment_types` (optional): List of allowed attachment extensions.
- `imap_archive` – Download an IMAP message and attachments and store them.
  - `host`: IMAP server hostname.
  - `username`: Login username.
  - `password`: Login password.
  - `port` (optional): IMAP SSL port, defaults to `993`.
  - `mailbox` (optional): Mailbox to select, defaults to `INBOX`.
  - `drive_folder_id` (optional): Drive folder ID for storage.
  - `local_dir` (optional): Local directory for storage.
  - `token` (optional): OAuth bearer token used for Drive uploads.
  - `save_attachments` (optional): Download attachments, defaults to `true`.
- `pdf_split` – Split a PDF file into smaller PDFs.
  - `output_dir`: Directory where split files are written.
  - `pattern` (optional): Regular expression marking the start of a new file.
  - `name_template` (optional): Template for output filenames.
  - `regex_fields` (optional): Mapping of field names to regex patterns to extract.
  - `table_fields` (optional): Fields to extract from table rows.
  - `parse_invoice` (optional): Parse invoice data from chunks.
  - `date_formats` (optional): Mapping of field names to `strftime` formats.
- `sheets_append` – Append data to a Google Sheet.
  - `sheet_id`: ID of the target spreadsheet.
  - `range`: Target range for the append.
  - `token` (optional): OAuth bearer token.
  - `fields` (optional): Ordered list of data keys if `values` not supplied.
- `slack_notify` – Send a notification to Slack via webhook.
  - `webhook_url`: Slack webhook URL.

