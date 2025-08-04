"""Core workflow engine for PyZap."""

import importlib
import logging
import re
import os
import threading
import time
import signal
from abc import ABC, abstractmethod
from email.message import EmailMessage
import smtplib
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any, Dict, List, Type

from .config import load_config

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
    def __init__(self, definition: Dict[str, Any], *, step_mode: bool = False):
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
        self.interval = int(trigger_conf.get("interval", 60))
        self.step_mode = step_mode

    def run(self) -> None:
        logging.info(
            "Running workflow %s using %s", self.id, type(self.trigger).__name__
        )
        logging.debug(
            "Trigger %s input config: %s",
            type(self.trigger).__name__,
            self.trigger.config,
        )
        if self.step_mode:
            input("Press Enter to poll trigger...")

        messages = self.trigger.poll()
        logging.info("Trigger returned %d messages", len(messages))
        logging.debug(
            "Trigger %s output payloads: %s",
            type(self.trigger).__name__,
            messages,
        )
        if self.step_mode:
            input("Press Enter to process messages...")
        for payload in messages:
            msg_id = payload.get("id")
            if msg_id and msg_id in self.seen_ids:
                continue
            if msg_id:
                self.seen_ids.add(msg_id)
            current = payload
            for action in self.actions:
                if self.step_mode:
                    input(f"Press Enter to run action {type(action).__name__}...")
                try:
                    from .formatter import normalize

                    normalized = normalize(current)
                    logging.debug(
                        "Action %s input payload: %s",
                        type(action).__name__,
                        normalized,
                    )
                    result = action.execute(normalized)
                    logging.debug(
                        "Action %s output payload: %s",
                        type(action).__name__,
                        result,
                    )
                    if isinstance(result, dict):
                        current = result
                except Exception as exc:  # pylint: disable=broad-except
                    logging.exception("Action %s failed: %s", action, exc)
                else:
                    logging.info(
                        "Action %s executed successfully", type(action).__name__
                    )
                    if self.step_mode:
                        input("Press Enter to continue...")


class WorkflowEngine:
    def __init__(self, config_path: str, *, step_mode: bool = False):
        self.config_path = config_path
        self.workflows: List[Workflow] = []
        self.step_mode = step_mode
        self.admin_email = None
        self.smtp_config: Dict[str, Any] = {}
        self.load_config()
        self._stop_event = threading.Event()
        self._last_run: Dict[str, float] = {}

    def load_config(self) -> None:
        data = load_config(self.config_path)
        if isinstance(data, list):
            config = {"workflows": data}
        else:
            config = data

        self.admin_email = config.get("admin_email")
        self.smtp_config = config.get("smtp", {})

        wf_defs = config.get("workflows", [])
        self.workflows = [Workflow(defn, step_mode=self.step_mode) for defn in wf_defs]

    def run_all(self) -> None:
        logging.debug("Engine cycle running %d workflows", len(self.workflows))
        for wf in self.workflows:
            last = self._last_run.get(wf.id, 0)
            if time.time() - last < wf.interval:
                continue
            self._run_workflow(wf)
            self._last_run[wf.id] = time.time()

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
        """Send a failure notification email to the administrator."""
        if not self.admin_email:
            logging.error("Admin email not configured")
            logging.error("Workflow %s failed after retries", workflow_id)
            return

        message = EmailMessage()
        message["Subject"] = f"PyZap workflow {workflow_id} failed"
        message["From"] = self.smtp_config.get("from_addr", self.admin_email)
        message["To"] = self.admin_email
        message.set_content(
            f"Workflow {workflow_id} failed after maximum retries."
        )

        host = self.smtp_config.get("host", "localhost")
        port = int(self.smtp_config.get("port", 25))
        username = self.smtp_config.get("username")
        password = self.smtp_config.get("password")
        use_tls = self.smtp_config.get("tls")

        try:
            with smtplib.SMTP(host, port) as smtp:
                if use_tls:
                    smtp.starttls()
                if username and password:
                    smtp.login(username, password)
                smtp.send_message(message)
                logging.info("Admin notification sent for workflow %s", workflow_id)
        except Exception as exc:  # pylint: disable=broad-except
            logging.exception("Failed to send admin notification: %s", exc)
        logging.error("Workflow %s failed after retries", workflow_id)

    def stop(self) -> None:
        self._stop_event.set()


def setup_logging(log_file: str = "pyzap.log", *, log_level: int = logging.INFO) -> None:
    handler = RotatingFileHandler(
        log_file, maxBytes=1_000_000, backupCount=3, encoding="utf-8"
    )
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[handler],
    )


def to_snake_case(name: str) -> str:
    """Convert CamelCase string to snake_case."""
    return re.sub(r'(?<!^)(?=[A-Z][a-z])', '_', name).lower()


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


def main_loop(
    config_path: str,
    *,
    log_level: str = "INFO",
    step_mode: bool = False,
    iterations: int = 0,
    repeat_interval: float = 1.0,
) -> None:
    numeric_level = getattr(logging, log_level.upper(), logging.INFO)
    setup_logging(log_level=numeric_level)
    load_plugins()
    engine = WorkflowEngine(config_path, step_mode=step_mode)

    stop_loop = False

    def _handle_sigterm(signum, frame):  # pylint: disable=unused-argument
        nonlocal stop_loop
        engine.stop()
        stop_loop = True

    signal.signal(signal.SIGTERM, _handle_sigterm)

    count = 0
    while not stop_loop and (iterations == 0 or count < iterations):
        try:
            engine.run_all()
            count += 1
            if not stop_loop and (iterations == 0 or count < iterations):
                time.sleep(repeat_interval)
        except KeyboardInterrupt:
            engine.stop()
            break


if __name__ == "__main__":
    cfg = os.environ.get("PYZAP_CONFIG", "config.json")
    main_loop(cfg)
