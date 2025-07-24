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

## Email polling triggers

Two built-in triggers allow fetching messages from email servers:

* `gmail_poll` &ndash; uses the Gmail API with an OAuth2 token. Provide a
  `token_file` path in the trigger configuration and optionally a search
  `query`.
* `imap_poll` &ndash; connects to any IMAP server using username and password.
  Required options are `host`, `username` and `password`. Optional keys are
  `mailbox` (defaults to `INBOX`) and `search` (defaults to `UNSEEN`).

## Logging

Runtime logs are written to `pyzap.log` with level `INFO`. Each workflow
reports when it polls for messages, the number of messages found and whether
actions succeed or fail. Each log entry now includes the date and time,
helping troubleshoot the engine while it runs in endless polling mode.
