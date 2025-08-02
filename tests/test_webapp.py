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


def test_create_workflow_via_api(tmp_path, monkeypatch):
    """Ensure the API saves workflows when config is a plain list."""
    cfg_path = tmp_path / "config.json"
    cfg_path.write_text("[]")
    monkeypatch.setattr("pyzap.webapp.CONFIG_PATH", str(cfg_path))

    client = app.test_client()
    resp = client.post(
        "/api/workflows",
        json={
            "id": "wf_api",
            "trigger": {"type": "manual", "query": "", "token_file": ""},
            "actions": [],
        },
    )
    assert resp.status_code == 200
    data = json.loads(cfg_path.read_text())
    assert data[0]["id"] == "wf_api"


def test_edit_workflow_via_form(tmp_path, monkeypatch):
    """Existing workflows can be modified via the HTML form."""
    cfg_path = tmp_path / "config.json"
    cfg_path.write_text(
        json.dumps(
            {
                "workflows": [
                    {
                        "id": "wf1",
                        "trigger": {
                            "type": "manual",
                            "query": "",
                            "token_file": "",
                        },
                        "actions": [],
                    }
                ]
            }
        )
    )
    monkeypatch.setattr("pyzap.webapp.CONFIG_PATH", str(cfg_path))

    client = app.test_client()
    resp = client.post(
        "/workflow/0",
        data={
            "id": "wf1_mod",
            "trigger_type": "manual",
            "trigger_query": "new-query",
            "trigger_token_file": "token.json",
            "actions": "[]",
        },
        follow_redirects=True,
    )
    assert resp.status_code == 200

    data = json.loads(cfg_path.read_text())
    wf = data["workflows"][0]
    assert wf["id"] == "wf1_mod"
    assert wf["trigger"]["query"] == "new-query"
    assert wf["trigger"]["token_file"] == "token.json"
