"""Core workflow engine for PyZap."""

import importlib
import json
import logging
import re
import os
import threading
import time
from abc import ABC, abstractmethod
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any, Dict, List, Type

# Plugin registries
TRIGGERS: Dict[str, Type["BaseTrigger"]] = {}
ACTIONS: Dict[str, Type["BaseAction"]] = {}


class BaseTrigger(ABC):
    """Abstract base class for triggers."""

    def __init__(self, config: Dict[str, Any]):
        self.config = config

    @abstractmethod
    def poll(self) -> List[Dict[str, Any]]:
        """Poll for new events and return a list of payloads."""
        raise NotImplementedError


class BaseAction(ABC):
    """Abstract base class for actions."""

    def __init__(self, params: Dict[str, Any]):
        self.params = params

    @abstractmethod
    def execute(self, data: Dict[str, Any]) -> None:
        """Execute the action on normalized data."""
        raise NotImplementedError


class Workflow:
    def __init__(self, definition: Dict[str, Any]):
        self.id = definition["id"]
        trigger_conf = definition["trigger"]
        trigger_cls = TRIGGERS.get(trigger_conf["type"])
        if not trigger_cls:
            raise ValueError(f"Unknown trigger type {trigger_conf['type']}")
        self.trigger = trigger_cls(trigger_conf)
        self.actions = []
        for action_def in definition.get("actions", []):
            action_cls = ACTIONS.get(action_def["type"])
            if not action_cls:
                raise ValueError(f"Unknown action type {action_def['type']}")
            self.actions.append(action_cls(action_def.get("params", {})))
        self.seen_ids = set()

    def run(self) -> None:
        logging.info("Running workflow %s using %s", self.id, type(self.trigger).__name__)
        messages = self.trigger.poll()
        logging.info("Trigger returned %d messages", len(messages))
        for payload in messages:
            msg_id = payload.get("id")
            if msg_id and msg_id in self.seen_ids:
                continue
            if msg_id:
                self.seen_ids.add(msg_id)
            for action in self.actions:
                try:
                    from .formatter import normalize

                    normalized = normalize(payload)
                    action.execute(normalized)
                    logging.info("Action %s executed successfully", type(action).__name__)
                except Exception as exc:  # pylint: disable=broad-except
                    logging.exception("Action %s failed: %s", action, exc)


class WorkflowEngine:
    def __init__(self, config_path: str):
        self.config_path = config_path
        self.workflows: List[Workflow] = []
        self.load_config()
        self._stop_event = threading.Event()

    def load_config(self) -> None:
        with open(self.config_path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        self.workflows = [Workflow(defn) for defn in data]

    def run_all(self) -> None:
        logging.info("Running %d workflows", len(self.workflows))
        threads = []
        for wf in self.workflows:
            t = threading.Thread(target=self._run_workflow, args=(wf,), daemon=True)
            threads.append(t)
            t.start()
        for t in threads:
            t.join()

    def _run_workflow(self, workflow: Workflow) -> None:
        retry = 0
        max_retries = 3
        while retry <= max_retries and not self._stop_event.is_set():
            try:
                workflow.run()
                logging.info("Workflow %s completed", workflow.id)
                break
            except Exception as exc:  # pylint: disable=broad-except
                retry += 1
                logging.exception("Workflow %s failed (%s). Retry %s/%s", workflow.id, exc, retry, max_retries)
                time.sleep(1)
        else:
            self.notify_admin(workflow.id)

    def notify_admin(self, workflow_id: str) -> None:
        # TODO: Send email via local SMTP
        logging.error("Workflow %s failed after retries", workflow_id)

    def stop(self) -> None:
        self._stop_event.set()


def setup_logging(log_file: str = "pyzap.log") -> None:
    handler = RotatingFileHandler(log_file, maxBytes=1_000_000, backupCount=3)
    logging.basicConfig(level=logging.INFO, handlers=[handler])


def to_snake_case(name: str) -> str:
    """Convert CamelCase string to snake_case."""
    # Example: "GmailPoll" -> "gmail_poll"
    return re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower()


def load_plugins() -> None:
    plugins_dir = Path(__file__).parent / "plugins"
    for path in plugins_dir.glob("*.py"):
        if path.name.startswith("__"):
            continue
        module_name = f"pyzap.plugins.{path.stem}"
        module = importlib.import_module(module_name)
        for attr in dir(module):
            obj = getattr(module, attr)
            if isinstance(obj, type) and issubclass(obj, BaseTrigger) and obj is not BaseTrigger:
                plugin_name = obj.__name__.replace("Trigger", "")
                TRIGGERS[to_snake_case(plugin_name)] = obj
            if isinstance(obj, type) and issubclass(obj, BaseAction) and obj is not BaseAction:
                plugin_name = obj.__name__.replace("Action", "")
                ACTIONS[to_snake_case(plugin_name)] = obj


def main_loop(config_path: str) -> None:
    setup_logging()
    load_plugins()
    engine = WorkflowEngine(config_path)
    while True:
        try:
            engine.run_all()
            time.sleep(1)
        except KeyboardInterrupt:
            engine.stop()
            break


if __name__ == "__main__":
    cfg = os.environ.get("PYZAP_CONFIG", "config.json")
    main_loop(cfg)
