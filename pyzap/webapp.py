"""Minimal Flask dashboard for PyZap.

This module now exposes a small interface to inspect, create and edit
workflow definitions stored in ``config.json``.  The aim is to guide the
user through the process of assembling a workflow without having to edit
the raw JSON by hand.
"""

import json

from flask import (
    Flask,
    jsonify,
    redirect,
    render_template_string,
    request,
    url_for,
)

from .config import load_config, save_config

app = Flask(__name__)
CONFIG_PATH = "config.json"

INDEX_TEMPLATE = """
<!doctype html>
<title>PyZap Workflows</title>
<h1>Workflows</h1>
<p><a href="{{ url_for('edit_workflow') }}">Nuovo workflow</a></p>
<ul>
{% for wf in workflows %}
    <li>
        {{ wf.id }} - {{ 'enabled' if wf.get('enabled', True) else 'disabled' }}
        [<a href="{{ url_for('edit_workflow', index=loop.index0) }}">modifica</a>]
    </li>
{% endfor %}
</ul>
"""

EDIT_TEMPLATE = """
<!doctype html>
<title>Workflow editor</title>
<h1>{{ 'Nuovo' if index is none else 'Modifica' }} workflow</h1>
<form method="post">
  <label>ID<br><input name="id" value="{{ wf.id }}" required></label><br>
  <h2>Trigger</h2>
  <label>Tipo<br><input name="trigger_type" value="{{ wf.trigger.type }}" required></label><br>
  <label>Query<br><input name="trigger_query" value="{{ wf.trigger.query }}"></label><br>
  <label>Token file<br><input name="trigger_token_file" value="{{ wf.trigger.token_file }}"></label><br>
  <h2>Azioni</h2>
  <p>Inserisci un array JSON di azioni.</p>
  <textarea name="actions" rows="10" cols="80">{{ wf.actions | tojson(indent=2) }}</textarea><br>
  <button type="submit">Salva</button>
</form>
<p><a href="{{ url_for('index') }}">Torna alla lista</a></p>
"""


def _get_workflows(cfg):
    """Extract the list of workflows from the loaded config."""
    return cfg.get("workflows", []) if isinstance(cfg, dict) else cfg


@app.route("/")
def index():
    cfg = load_config(CONFIG_PATH)
    workflows = _get_workflows(cfg)
    return render_template_string(INDEX_TEMPLATE, workflows=workflows)


@app.route("/workflow/new", methods=["GET", "POST"])
@app.route("/workflow/<int:index>", methods=["GET", "POST"])
def edit_workflow(index=None):
    cfg = load_config(CONFIG_PATH)
    workflows = _get_workflows(cfg)

    if request.method == "POST":
        wf = {
            "id": request.form["id"],
            "trigger": {
                "type": request.form.get("trigger_type", ""),
                "query": request.form.get("trigger_query", ""),
                "token_file": request.form.get("trigger_token_file", ""),
            },
            "actions": json.loads(request.form.get("actions", "[]")),
        }
        if index is None:
            workflows.append(wf)
        else:
            workflows[index] = wf
        if isinstance(cfg, dict):
            cfg["workflows"] = workflows
            save_config(CONFIG_PATH, cfg)
        else:
            save_config(CONFIG_PATH, workflows)
        return redirect(url_for("index"))

    wf = (
        workflows[index]
        if index is not None and index < len(workflows)
        else {"id": "", "trigger": {"type": "", "query": "", "token_file": ""}, "actions": []}
    )
    return render_template_string(EDIT_TEMPLATE, wf=wf, index=index)


@app.route("/api/workflows", methods=["POST"])
def create_workflow_api():
    """Legacy API endpoint used by tests or scripts."""
    data = request.get_json()
    cfg = load_config(CONFIG_PATH)
    workflows = _get_workflows(cfg)
    workflows.append(data)
    if isinstance(cfg, dict):
        cfg["workflows"] = workflows
        save_config(CONFIG_PATH, cfg)
    else:
        save_config(CONFIG_PATH, workflows)
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    app.run(debug=True)
