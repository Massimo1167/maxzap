import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pyzap.config import load_config


def test_load_config_strips_comment_keys(tmp_path):
    data = {
        "_comment": "top",
        "value": 1,
        "nested": {"x": 2, "_note": "n"},
        "items": [{"a": 1, "_b": 2}, 3],
    }
    path = tmp_path / "cfg.json"
    path.write_text(json.dumps(data))

    cfg = load_config(str(path))
    assert "_comment" not in cfg
    assert "value" in cfg and cfg["value"] == 1
    assert "_note" not in cfg["nested"]
    assert cfg["nested"]["x"] == 2
    assert cfg["items"][0] == {"a": 1}
    assert cfg["items"][1] == 3


def test_load_config_env_vars_and_comments(monkeypatch, tmp_path):
    monkeypatch.setenv("VAL", "42")
    data = {"num": "${VAL}", "_c": "x"}
    path = tmp_path / "cfg.json"
    path.write_text(json.dumps(data))
    cfg = load_config(str(path))
    assert cfg == {"num": "42"}


def test_load_config_invalid_json(tmp_path):
    path = tmp_path / "bad.json"
    path.write_text("{bad json")

    with pytest.raises(SystemExit) as excinfo:
        load_config(str(path))

    assert str(excinfo.value).startswith(f"Invalid JSON in {path}:")
