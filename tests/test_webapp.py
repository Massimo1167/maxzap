"""Tests for the minimal GUI web application."""

import json

from pyzap.webapp import app, CONFIG_PATH


def test_index_route(tmp_path, monkeypatch):
    cfg_path = tmp_path / "config.json"
    cfg_path.write_text(json.dumps({"workflows": []}))
    monkeypatch.setattr("pyzap.webapp.CONFIG_PATH", str(cfg_path))

    client = app.test_client()
    resp = client.get("/")
    assert resp.status_code == 200
    assert b"Workflows" in resp.data


def test_create_workflow_via_form(tmp_path, monkeypatch):
    cfg_path = tmp_path / "config.json"
    cfg_path.write_text(json.dumps({"workflows": []}))
    monkeypatch.setattr("pyzap.webapp.CONFIG_PATH", str(cfg_path))

    client = app.test_client()
    resp = client.post(
        "/workflow/new",
        data={
            "id": "wf1",
            "trigger_type": "manual",
            "trigger_query": "",
            "trigger_token_file": "",
            "actions": "[]",
        },
        follow_redirects=True,
    )
    assert resp.status_code == 200

    data = json.loads(cfg_path.read_text())
    assert data["workflows"][0]["id"] == "wf1"


def test_invalid_json_actions(tmp_path, monkeypatch):
    cfg_path = tmp_path / "config.json"
    cfg_path.write_text(json.dumps({"workflows": []}))
    monkeypatch.setattr("pyzap.webapp.CONFIG_PATH", str(cfg_path))

    client = app.test_client()
    resp = client.post(
        "/workflow/new",
        data={
            "id": "wf1",
            "trigger_type": "manual",
            "trigger_query": "",
            "trigger_token_file": "",
            "actions": "[invalid",
        },
    )
    assert resp.status_code == 200
    assert b"Invalid JSON" in resp.data
