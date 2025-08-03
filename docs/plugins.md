# Plugin Reference

This page lists all available triggers and actions provided by PyZap.

## Triggers

- `excel_poll` – Poll an Excel workbook for newly appended rows.
- `excel_row_added` – Detect new rows with optional advanced filtering.
- `excel_cell_change` – Trigger when monitored cells change value.
- `excel_file_updated` – Trigger when the Excel file modification time changes.
- `excel_attachment_row` – Trigger on new rows where an attachment column contains data.
- `gmail_poll` – Poll Gmail using the Gmail API.
- `imap_poll` – Poll an IMAP server for new messages.

## Actions

- `excel_append` – Append data to an Excel workbook.
- `excel_write_row` – Create or update rows in an Excel file.
- `email_send` – Send an email using SMTP.
- `db_save` – Save data into a SQLite database.
- `file_create` – Create a file from row data.
- `attachment_download` – Download attachments referenced in a row.
- `g_drive_upload` – Upload a file to Google Drive.
- `gmail_archive` – Download a Gmail message and attachments and store them.
- `imap_archive` – Download an IMAP message and attachments and store them.
- `pdf_split` – Split a PDF file into smaller PDFs.
- `sheets_append` – Append data to a Google Sheet.
- `slack_notify` – Send a notification to Slack via webhook.

