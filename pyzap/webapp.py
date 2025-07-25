"""Minimal Flask dashboard for PyZap."""

from flask import Flask, jsonify, render_template_string, request

from .config import load_config, save_config

app = Flask(__name__)
CONFIG_PATH = "config.json"

TEMPLATE = """
<!doctype html>
<title>PyZap Workflows</title>
<h1>Workflows</h1>
<ul>
{% for wf in workflows %}
    <li>{{ wf.id }} - {{ 'enabled' if wf.get('enabled', True) else 'disabled' }}</li>
{% endfor %}
</ul>
"""


@app.route("/")
def index():
    cfg = load_config(CONFIG_PATH)
    workflows = cfg.get("workflows", []) if isinstance(cfg, dict) else cfg
    return render_template_string(TEMPLATE, workflows=workflows)


@app.route("/api/workflows", methods=["POST"])
def create_workflow():
    data = request.get_json()
    cfg = load_config(CONFIG_PATH)
    workflows = cfg.get("workflows", []) if isinstance(cfg, dict) else cfg
    workflows.append(data)
    if isinstance(cfg, dict):
        cfg["workflows"] = workflows
        save_config(CONFIG_PATH, cfg)
    else:
        save_config(CONFIG_PATH, workflows)
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    app.run(debug=True)
