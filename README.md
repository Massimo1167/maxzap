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
