import json
import sys
from pathlib import Path
import threading
import time

# Ensure project root on the path for test execution environments
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pyzap import core


class DummyTrigger(core.BaseTrigger):
    def __init__(self, config):
        super().__init__(config)
        self.calls = 0

    def poll(self):
        self.calls += 1
        return [{"id": "1"}, {"id": "2"}]


class DummyAction(core.BaseAction):
    def __init__(self, params):
        super().__init__(params)
        self.executed = []

    def execute(self, data):
        self.executed.append(data)


def test_workflow_run(monkeypatch):
    monkeypatch.setitem(core.TRIGGERS, "dummy", DummyTrigger)
    monkeypatch.setitem(core.ACTIONS, "dummy", DummyAction)

    wf_def = {"id": "wf", "trigger": {"type": "dummy"}, "actions": [{"type": "dummy"}]}
    wf = core.Workflow(wf_def)
    wf.run()
    action = wf.actions[0]
    assert len(action.executed) == 2

    # running again should skip already seen ids
    wf.run()
    assert len(action.executed) == 2


def test_engine_interval(monkeypatch, tmp_path):
    monkeypatch.setitem(core.TRIGGERS, "dummy", DummyTrigger)

    config = [{"id": "wf", "trigger": {"type": "dummy", "interval": 10}}]
    cfg_path = tmp_path / "config.json"
    cfg_path.write_text(json.dumps(config))

    engine = core.WorkflowEngine(str(cfg_path))
    called = []
    monkeypatch.setattr(engine, "_run_workflow", lambda wf: called.append(wf.id))

    monkeypatch.setattr(core.time, "time", lambda: 100)
    engine.run_all()
    assert called == ["wf"]

    # within interval, should not run again
    monkeypatch.setattr(core.time, "time", lambda: 105)
    engine.run_all()
    assert called == ["wf"]

    # after interval passed
    monkeypatch.setattr(core.time, "time", lambda: 120)
    engine.run_all()
    assert called == ["wf", "wf"]


def test_notify_admin(monkeypatch, tmp_path):
    monkeypatch.setitem(core.TRIGGERS, "dummy", DummyTrigger)
    config = {
        "admin_email": "admin@example.com",
        "smtp": {"host": "localhost", "port": 25},
        "workflows": []
    }
    cfg_path = tmp_path / "config.json"
    cfg_path.write_text(json.dumps(config))

    engine = core.WorkflowEngine(str(cfg_path))

    sent = {}

    class DummySMTP:
        def __init__(self, host, port):
            sent["host"] = host
            sent["port"] = port

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            pass

        def send_message(self, msg):
            sent["to"] = msg["To"]
            sent["subject"] = msg["Subject"]

    monkeypatch.setattr(core.smtplib, "SMTP", DummySMTP)

    engine.notify_admin("wf1")

    assert sent["to"] == "admin@example.com"


class ReturnAction(core.BaseAction):
    def execute(self, data):
        return {"x": 1}


class CaptureAction(core.BaseAction):
    def __init__(self, params):
        super().__init__(params)
        self.received = None

    def execute(self, data):
        self.received = data


def test_workflow_pass_metadata(monkeypatch):
    monkeypatch.setitem(core.TRIGGERS, "dummy", DummyTrigger)
    monkeypatch.setitem(core.ACTIONS, "ret", ReturnAction)
    monkeypatch.setitem(core.ACTIONS, "cap", CaptureAction)

    wf_def = {
        "id": "wf", 
        "trigger": {"type": "dummy"},
        "actions": [{"type": "ret"}, {"type": "cap"}]
    }
    wf = core.Workflow(wf_def)
    wf.run()
    cap = wf.actions[1]
    assert cap.received == {"x": 1}


def test_main_loop_sigterm(monkeypatch, tmp_path):
    cfg_path = tmp_path / "config.json"
    cfg_path.write_text("[]")

    created = {}

    class DummyEngine:
        def __init__(self, path, *, step_mode=False):
            created["engine"] = self
            self.stop_called = False
            self.calls = 0

        def run_all(self):
            self.calls += 1
            if self.calls == 1 and handlers.get("handler"):
                handlers["handler"](core.signal.SIGTERM, None)
            elif self.calls > 1:
                raise RuntimeError("loop did not stop")

        def stop(self):
            self.stop_called = True

    monkeypatch.setattr(core, "load_plugins", lambda: None)
    handlers = {}

    def fake_signal(sig, func):
        handlers["handler"] = func

    monkeypatch.setattr(core.signal, "signal", fake_signal)
    monkeypatch.setattr(core.time, "sleep", lambda s: None)

    monkeypatch.setattr(core, "WorkflowEngine", DummyEngine)

    core.main_loop(str(cfg_path))

    assert handlers.get("handler") is not None
    assert created["engine"].stop_called
