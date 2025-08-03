"""Tests for the minimal GUI web application."""
import json
import re
from io import BytesIO

from pyzap.webapp import app


def _get_csrf_token(client, path):
    """Retrieve CSRF token from form at ``path``."""
    resp = client.get(path)
    assert resp.status_code == 200
    match = re.search(r'name="csrf_token" value="([^"]+)"', resp.data.decode())
    assert match
    return match.group(1)


def _set_config_path(client, path):
    with client.session_transaction() as sess:
        sess["config_path"] = path


def test_index_route(tmp_path):
    cfg_path = tmp_path / "config.json"
    cfg_path.write_text(json.dumps({"workflows": []}))

    client = app.test_client()
    _set_config_path(client, str(cfg_path))
    resp = client.get("/")
    assert resp.status_code == 200
    assert b"Workflows" in resp.data


def test_create_workflow_via_form(tmp_path):
    cfg_path = tmp_path / "config.json"
    cfg_path.write_text(json.dumps({"workflows": []}))

    client = app.test_client()
    _set_config_path(client, str(cfg_path))
    token = _get_csrf_token(client, "/workflow/new")
    resp = client.post(
        "/workflow/new",
        data={
            "id": "wf1",
            "trigger": json.dumps({"type": "manual", "query": "", "token_file": ""}),
            "actions": "[]",
            "csrf_token": token,
        },
        follow_redirects=True,
    )
    assert resp.status_code == 200

    data = json.loads(cfg_path.read_text())
    assert data["workflows"][0]["id"] == "wf1"


def test_invalid_json_actions(tmp_path):
    cfg_path = tmp_path / "config.json"
    cfg_path.write_text(json.dumps({"workflows": []}))

    client = app.test_client()
    _set_config_path(client, str(cfg_path))
    token = _get_csrf_token(client, "/workflow/new")
    resp = client.post(
        "/workflow/new",
        data={
            "id": "wf1",
            "trigger": json.dumps({"type": "manual", "query": "", "token_file": ""}),
            "actions": "[invalid",
            "csrf_token": token,
        },
    )
    assert resp.status_code == 200
    assert b"Invalid JSON" in resp.data


def test_create_workflow_via_api(tmp_path):
    """Ensure the API saves workflows when config is a plain list."""
    cfg_path = tmp_path / "config.json"
    cfg_path.write_text("[]")

    client = app.test_client()
    _set_config_path(client, str(cfg_path))
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


def test_edit_workflow_via_form(tmp_path):
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

    client = app.test_client()
    _set_config_path(client, str(cfg_path))
    token = _get_csrf_token(client, "/workflow/0")
    resp = client.post(
        "/workflow/0",
        data={
            "id": "wf1_mod",
            "trigger": json.dumps({"type": "manual", "query": "new-query", "token_file": "token.json"}),
            "actions": "[]",
            "csrf_token": token,
        },
        follow_redirects=True,
    )
    assert resp.status_code == 200

    data = json.loads(cfg_path.read_text())
    wf = data["workflows"][0]
    assert wf["id"] == "wf1_mod"
    assert wf["trigger"]["query"] == "new-query"
    assert wf["trigger"]["token_file"] == "token.json"


def test_upload_config(tmp_path):
    cfg_path = tmp_path / "uploaded.json"
    client = app.test_client()
    data = BytesIO(json.dumps({"workflows": []}).encode("utf-8"))
    resp = client.post(
        "/config/upload",
        data={"config_file": (data, "cfg.json"), "dest_path": str(cfg_path)},
        content_type="multipart/form-data",
        follow_redirects=True,
    )
    assert resp.status_code == 200
    assert cfg_path.exists()
    with client.session_transaction() as sess:
        assert sess["config_path"] == str(cfg_path)


def test_config_save_same_path(tmp_path):
    cfg_path = tmp_path / "config.json"
    client = app.test_client()
    _set_config_path(client, str(cfg_path))
    resp = client.post(
        "/config/save",
        json={"config": {"workflows": [{"id": "w1"}]}},
    )
    assert resp.status_code == 200
    data = json.loads(cfg_path.read_text())
    assert data["workflows"][0]["id"] == "w1"


def test_config_save_new_path(tmp_path):
    old_path = tmp_path / "old.json"
    old_path.write_text("[]")
    new_path = tmp_path / "new.json"

    client = app.test_client()
    _set_config_path(client, str(old_path))
    resp = client.post(
        "/config/save",
        json={"config": {"workflows": []}, "new_path": str(new_path)},
    )
    assert resp.status_code == 200
    assert new_path.exists()
    with client.session_transaction() as sess:
        assert sess["config_path"] == str(new_path)


def test_help_plugins_route():
    client = app.test_client()
    resp = client.get("/help/plugins")
    assert resp.status_code == 200
    assert b"Trigger Disponibili" in resp.data
    assert b"host" in resp.data
    assert b"folder_id" in resp.data

