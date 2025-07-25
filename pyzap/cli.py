"""Command line interface for PyZap."""

import argparse
import json

from .core import main_loop
from .config import load_config, save_config
from .webapp import app as webapp_app

def _get_workflows(path: str):
    cfg = load_config(path)
    return cfg.get("workflows", []) if isinstance(cfg, dict) else cfg


def list_workflows(args: argparse.Namespace) -> None:
    workflows = _get_workflows(args.config)
    for wf in workflows:
        status = "enabled" if wf.get("enabled", True) else "disabled"
        print(f"{wf['id']} - {status}")


def create_workflow(args: argparse.Namespace) -> None:
    config = load_config(args.config)
    workflows = config.get("workflows", []) if isinstance(config, dict) else config
    with open(args.file, "r", encoding="utf-8") as fh:
        new_wf = json.load(fh)
    workflows.append(new_wf)
    if isinstance(config, dict):
        config["workflows"] = workflows
        save_config(args.config, config)
    else:
        save_config(args.config, workflows)
    print(f"Added workflow {new_wf['id']}")


def set_workflow_state(args: argparse.Namespace, enabled: bool) -> None:
    config = load_config(args.config)
    workflows = config.get("workflows", []) if isinstance(config, dict) else config
    for wf in workflows:
        if wf["id"] == args.id:
            wf["enabled"] = enabled
            break
    else:
        raise SystemExit(f"Workflow {args.id} not found")
    if isinstance(config, dict):
        config["workflows"] = workflows
        save_config(args.config, config)
    else:
        save_config(args.config, workflows)
    state = "enabled" if enabled else "disabled"
    print(f"Workflow {args.id} {state}")


def run_engine(args: argparse.Namespace) -> None:
    """Starts the main workflow engine."""
    print("Starting PyZap engine...")
    main_loop(
        args.config,
        log_level=args.log_level,
        step_mode=args.step,
    )


def run_dashboard(args: argparse.Namespace) -> None:
    """Starts the Flask web dashboard."""
    print("Starting PyZap dashboard on http://127.0.0.1:5000")
    webapp_app.run(debug=True)


def main() -> None:
    parser = argparse.ArgumentParser(prog="pyzap")
    parser.add_argument("config", nargs="?", default="config.json", help="Config file path")
    sub = parser.add_subparsers(dest="command")

    sub_list = sub.add_parser("list")
    sub_list.set_defaults(func=list_workflows)

    sub_create = sub.add_parser("create")
    sub_create.add_argument("file")
    sub_create.set_defaults(func=create_workflow)

    sub_enable = sub.add_parser("enable")
    sub_enable.add_argument("id")
    sub_enable.set_defaults(func=lambda a: set_workflow_state(a, True))

    sub_disable = sub.add_parser("disable")
    sub_disable.add_argument("id")
    sub_disable.set_defaults(func=lambda a: set_workflow_state(a, False))

    sub_run = sub.add_parser("run")
    sub_run.add_argument(
        "--log-level",
        default="INFO",
        help="Logging level (DEBUG, INFO, WARNING, ERROR)",
    )
    sub_run.add_argument(
        "--step",
        action="store_true",
        help="Pause for input between workflow steps",
    )
    sub_run.set_defaults(func=run_engine)

    sub_dashboard = sub.add_parser("dashboard", help="Run the web dashboard")
    sub_dashboard.set_defaults(func=run_dashboard)

    args = parser.parse_args()
    if hasattr(args, "func"):
        args.func(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
