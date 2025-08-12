# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

PyZap is a monolithic workflow automation tool inspired by Zapier. It implements a plugin-based architecture with triggers and actions, a command line interface, and a Flask web dashboard for configuration.

## Common Commands

### Running Tests
```bash
pytest -vv
```

### Running the Application
```bash
# Start the workflow engine
python -m pyzap run --log-level INFO

# Start the web dashboard
python -m pyzap dashboard

# Other CLI commands
python -m pyzap list                    # List workflows
python -m pyzap create <workflow.json>  # Create workflow from file
python -m pyzap enable <workflow_id>    # Enable workflow
python -m pyzap disable <workflow_id>   # Disable workflow
```

### CLI Options for Engine
- `--log-level DEBUG|INFO|WARNING|ERROR` - Set logging verbosity
- `--step` - Pause for input between workflow steps (debugging)
- `--iterations N` - Run N cycles (0 = run forever)
- `--repeat-interval N` - Delay between cycles in seconds

### Installing Dependencies
```bash
pip install -r requirements.txt
```

## Architecture

### Core Components

- **`pyzap/core.py`** - Workflow engine and main execution loop
  - `BaseTrigger` and `BaseAction` abstract classes
  - `Workflow` class manages trigger + actions execution
  - `WorkflowEngine` handles multiple workflows with retry logic
  - Plugin registry system (`TRIGGERS` and `ACTIONS` dictionaries)

- **`pyzap/cli.py`** - Command line interface with argparse
- **`pyzap/webapp.py`** - Flask web dashboard for workflow configuration
- **`pyzap/config.py`** - Configuration loading/saving utilities
- **`pyzap/formatter.py`** - Data transformation utilities between triggers and actions

### Plugin Architecture

Plugins are auto-discovered from `pyzap/plugins/` directory:
- Triggers extend `BaseTrigger` with `poll()` method returning list of payloads
- Actions extend `BaseAction` with `execute(data)` method
- Plugin classes are registered automatically using naming convention (e.g., `GmailPollTrigger` → `gmail_poll`)

### Key Plugin Types

**Triggers:**
- `gmail_poll` - Gmail API polling with OAuth2
- `imap_poll` - Generic IMAP server polling
- `excel_poll` - Monitor Excel files for changes
- `excel_watch` - File system watching for Excel changes

**Actions:**
- `gmail_archive` - Archive Gmail messages to Google Drive or local storage
- `imap_archive` - Archive IMAP messages locally
- `excel_append` - Append data to Excel workbooks with date formatting
- `sheets_append` - Append to Google Sheets
- `pdf_split` - Split PDFs and extract invoice data
- `slack_notify` - Send Slack notifications

### Configuration Structure

Configurations support global settings and workflow lists:

```json
{
  "admin_email": "admin@example.com",
  "smtp": { ... },
  "workflows": [
    {
      "id": "unique-workflow-id",
      "trigger": { "type": "gmail_poll", ... },
      "actions": [
        { "type": "gmail_archive", "params": { ... } },
        { "type": "excel_append", "params": { ... } }
      ]
    }
  ]
}
```

### Data Flow

1. Triggers return lists of normalized payloads with common fields (`id`, `subject`, `body`, etc.)
2. `formatter.normalize()` standardizes data between trigger and action
3. Actions receive normalized data and can return updated payloads for chaining
4. Workflows track `seen_ids` to prevent duplicate processing

### Web Dashboard

- Flask app with CSRF protection
- Dynamic forms for trigger/action parameter configuration
- Plugin introspection for automatic UI generation
- Configuration file upload/download
- Session-based config path management

### Error Handling

- Workflows retry failed executions up to 3 times
- Admin email notifications for persistent failures
- Comprehensive logging to `pyzap.log` with rotation
- Step mode for debugging workflow execution

## Development Notes

### Adding New Plugins

1. Create plugin file in `pyzap/plugins/`
2. Extend `BaseTrigger` or `BaseAction`
3. Use naming convention: `ClassNameTrigger` or `ClassNameAction`
4. Document parameters in docstrings for web UI auto-generation
5. Plugin will be auto-registered on startup

### Configuration Files

Multiple configuration files are used for different environments:
- `config.json.example` - Template configuration
- `config.imap.json` - IMAP-specific setup
- `config.azienda.agricola-*.json` - Business-specific configs

### Authentication

Gmail and Google Drive plugins require OAuth2 tokens:
1. Generate `credentials.json` from Google Cloud Console
2. Run `python get_gmail_token.py` to create `token.json`
3. Reference token files in trigger configurations

### Testing

Tests use pytest and cover:
- Core workflow engine functionality
- Plugin implementations
- Web dashboard routes and forms
- Configuration loading/saving
- Excel operations with file locking