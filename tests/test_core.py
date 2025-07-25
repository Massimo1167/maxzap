import json
import sys
from pathlib import Path

import threading

from pyzap import core

# Ensure project root on the path for test execution environments
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


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
