# PyZap

PyZap is a small command line application for automating personal workflows.

## Project Layout

- `pyzap/` - Python package containing the library and CLI entry points.
- `workflows/` - Example workflow files that can be enabled or customized.
- `README.md` - Project documentation.

## Usage

Install the project locally and run the CLI:

```bash
pip install -e .
pyzap --help
```

To enable and run a workflow:

```bash
pyzap run my_workflow
```

Workflows can be placed in the `workflows/` directory and referenced by name.
