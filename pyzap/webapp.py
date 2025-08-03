import json
import inspect
import re
from flask import (
    Flask,
    jsonify,
    redirect,
    render_template,
    request,
    url_for,
)
from flask_wtf import CSRFProtect
from .core import ACTIONS, TRIGGERS, BaseAction, BaseTrigger, load_plugins

# Assumendo che queste funzioni esistano nel tuo progetto
# Se non esistono, puoi sostituirle con semplici open/read/write
# from .config import load_config, save_config

def load_config(path):
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {"workflows": []}

def save_config(path, data):
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


app = Flask(__name__)
app.secret_key = "dev-secret-key"
csrf = CSRFProtect(app)
CONFIG_PATH = "azienda.agricola-splitpdf.json" # Usa il tuo file di config

def _get_workflows(cfg):
    """Estrae la lista di workflow dalla configurazione caricata."""
    return cfg.get("workflows", []) if isinstance(cfg, dict) else cfg

def _save_config(cfg):
    """Salva l'intera configurazione su CONFIG_PATH."""
    save_config(CONFIG_PATH, cfg)


def _extract_params(cls, is_trigger):
    """Return list of {'name':..., 'desc':...} for plugin class."""
    doc = inspect.getdoc(cls.poll if is_trigger else cls.execute) or inspect.getdoc(cls) or ""
    params = []
    lines = doc.splitlines()
    pattern = re.compile(r"- ``([^`]+)``: (.*)")
    i = 0
    while i < len(lines):
        match = pattern.match(lines[i].strip())
        if match:
            name = match.group(1)
            desc = match.group(2).strip()
            i += 1
            while i < len(lines) and lines[i].startswith(" "):
                desc += " " + lines[i].strip()
                i += 1
            params.append({"name": name, "desc": desc})
        else:
            i += 1
    if not params:
        source = inspect.getsource(cls)
        matches = re.findall(r"self\.(?:config|params)\.get\(\"([^\"]+)\"", source)
        params = [{"name": p, "desc": ""} for p in sorted(set(matches))]
    return params


def get_plugins_info():
    """Return metadata for all loaded trigger and action plugins."""
    load_plugins()
    triggers = [
        {"name": name, "params": _extract_params(cls, True)}
        for name, cls in sorted(TRIGGERS.items())
    ]
    actions = [
        {"name": name, "params": _extract_params(cls, False)}
        for name, cls in sorted(ACTIONS.items())
    ]
    return {"triggers": triggers, "actions": actions}


@app.route("/")
def index():
    cfg = load_config(CONFIG_PATH)
    workflows = _get_workflows(cfg)
    return render_template("index.html", cfg=cfg, workflows=workflows)


@app.route("/workflow/new", methods=["GET", "POST"])
@app.route("/workflow/<int:index>", methods=["GET", "POST"])
def edit_workflow(index=None):
    cfg = load_config(CONFIG_PATH)
    workflows = _get_workflows(cfg)

    if request.method == "POST":
        # Support legacy simple form used in tests
        if "trigger_type" in request.form:
            try:
                actions = json.loads(request.form.get("actions", "[]"))
            except json.JSONDecodeError:
                return "Invalid JSON"

            wf = {
                "id": request.form.get("id"),
                "trigger": {
                    "type": request.form.get("trigger_type"),
                    "query": request.form.get("trigger_query"),
                    "token_file": request.form.get("trigger_token_file"),
                },
                "actions": actions,
            }

            if index is None:
                workflows.append(wf)
            else:
                workflows[index] = wf

            cfg['workflows'] = workflows
            _save_config(cfg)
            return redirect(url_for("index"))

        # Ricostruisci le impostazioni globali
        cfg['admin_email'] = request.form.get('admin_email', '')
        if 'smtp' not in cfg:
            cfg['smtp'] = {}
        cfg['smtp']['host'] = request.form.get('smtp_host', '')
        cfg['smtp']['port'] = request.form.get('smtp_port', '')
        cfg['smtp']['username'] = request.form.get('smtp_username', '')
        cfg['smtp']['password'] = request.form.get('smtp_password', '')

        # Ricostruisci il workflow
        wf = {
            "id": request.form.get("id"),
            "trigger": {},
            "actions": []
        }

        # Ricostruisci il trigger dai parametri del form
        trigger_keys = [k for k in request.form if k.startswith('trigger_param_key_')]
        for key_field in trigger_keys:
            idx = key_field.rpartition('_')[-1]
            key = request.form[f'trigger_param_key_{idx}']
            value = request.form[f'trigger_param_value_{idx}']
            if key:
                wf['trigger'][key] = value

        # Converte valori numerici dove possibile
        if wf['trigger'].get('max_results'):
            wf['trigger']['max_results'] = int(wf['trigger']['max_results'])
        if wf['trigger'].get('interval'):
            wf['trigger']['interval'] = int(wf['trigger']['interval'])

        # Ricostruisci le azioni
        action_indices = sorted(list(set([k.split('_')[1] for k in request.form if k.startswith('action_')])))
        for i in action_indices:
            action_type = request.form.get(f'action_{i}_type')
            if not action_type:
                continue

            action = {"type": action_type, "params": {}}
            param_keys = [k for k in request.form if k.startswith(f'action_{i}_param_key_')]

            for key_field in param_keys:
                param_idx = key_field.rpartition('_')[-1]
                key = request.form[f'action_{i}_param_key_{param_idx}']
                value = request.form[f'action_{i}_param_value_{param_idx}']
                if key:
                    # Tenta di convertire a booleano o numero se appropriato
                    if value.lower() == 'true':
                        action['params'][key] = True
                    elif value.lower() == 'false':
                        action['params'][key] = False
                    else:
                        action['params'][key] = value

            wf['actions'].append(action)

        if index is None:
            workflows.append(wf)
        else:
            workflows[index] = wf

        cfg['workflows'] = workflows
        _save_config(cfg)
        return redirect(url_for("index"))

    # Metodo GET
    if index is not None and index < len(workflows):
        wf = workflows[index]
        is_new = False
    else:
        wf = {"id": "", "trigger": {}, "actions": []}
        is_new = True

    return render_template("edit_workflow.html", cfg=cfg, wf=wf, index=index, is_new=is_new)


@csrf.exempt
@app.route("/api/workflows", methods=["POST"])
def create_workflow_api():
    """Endpoint API legacy per test o script."""
    data = request.get_json()
    cfg = load_config(CONFIG_PATH)
    workflows = _get_workflows(cfg)
    workflows.append(data)
    if isinstance(cfg, dict):
        cfg['workflows'] = workflows
    else:
        cfg = workflows
    _save_config(cfg)
    return jsonify({"status": "ok"})


@app.route("/help/plugins")
def help_plugins():
    info = get_plugins_info()
    return render_template("help_plugins.html", **info)


if __name__ == "__main__":
    app.run(debug=True)