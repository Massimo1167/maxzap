"""Command line interface for PyZap."""

import argparse
import json
from pathlib import Path

from .core import main_loop


def load_config(path: str) -> list:
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def save_config(path: str, workflows: list) -> None:
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(workflows, fh, indent=2)


def list_workflows(args: argparse.Namespace) -> None:
    workflows = load_config(args.config)
    for wf in workflows:
        status = "enabled" if wf.get("enabled", True) else "disabled"
        print(f"{wf['id']} - {status}")


def create_workflow(args: argparse.Namespace) -> None:
    workflows = load_config(args.config)
    with open(args.file, "r", encoding="utf-8") as fh:
        new_wf = json.load(fh)
    workflows.append(new_wf)
    save_config(args.config, workflows)
    print(f"Added workflow {new_wf['id']}")


def set_workflow_state(args: argparse.Namespace, enabled: bool) -> None:
    workflows = load_config(args.config)
    for wf in workflows:
        if wf["id"] == args.id:
            wf["enabled"] = enabled
            break
    else:
        raise SystemExit(f"Workflow {args.id} not found")
    save_config(args.config, workflows)
    state = "enabled" if enabled else "disabled"
    print(f"Workflow {args.id} {state}")


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
    sub_run.add_argument("id")

    args = parser.parse_args()
    if args.command == "run":
        main_loop(args.config)
        return
    if hasattr(args, "func"):
        args.func(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
