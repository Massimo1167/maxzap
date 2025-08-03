import json
from flask import (
    Flask,
    jsonify,
    redirect,
    render_template,
    request,
    url_for,
)
from flask_wtf import CSRFProtect

from .core import load_plugins, TRIGGERS, ACTIONS

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

# Load available plugins at startup so TRIGGERS and ACTIONS are populated
load_plugins()
CONFIG_PATH = "azienda.agricola-splitpdf.json" # Usa il tuo file di config

def _get_workflows(cfg):
    """Estrae la lista di workflow dalla configurazione caricata."""
    return cfg.get("workflows", []) if isinstance(cfg, dict) else cfg

def _save_config(cfg):
    """Salva l'intera configurazione su CONFIG_PATH."""
    save_config(CONFIG_PATH, cfg)


def get_plugins_help():
    """Collect plugin names and their docstrings for triggers and actions."""
    plugins = {"triggers": [], "actions": []}
    for name, cls in TRIGGERS.items():
        plugins["triggers"].append({"name": name, "doc": cls.__doc__ or ""})
    for name, cls in ACTIONS.items():
        plugins["actions"].append({"name": name, "doc": cls.__doc__ or ""})
    return plugins


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
    plugin_help = get_plugins_help()
    is_new = index is None or index >= len(workflows)

    if request.method == "POST":
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

        # Campi legacy per il trigger
        if request.form.get("trigger_type"):
            wf['trigger']['type'] = request.form.get("trigger_type")
        if request.form.get("trigger_query"):
            wf['trigger']['query'] = request.form.get("trigger_query")
        if request.form.get("trigger_token_file"):
            wf['trigger']['token_file'] = request.form.get("trigger_token_file")

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
        if 'actions' in request.form:
            try:
                wf['actions'] = json.loads(request.form['actions'])
            except json.JSONDecodeError:
                return render_template(
                    "edit_workflow.html",
                    cfg=cfg,
                    wf=wf,
                    index=index,
                    is_new=is_new,
                    plugins=plugin_help,
                    error="Invalid JSON",
                )
        else:
            action_indices = sorted(
                list(set([k.split('_')[1] for k in request.form if k.startswith('action_')]))
            )
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
        elif index < len(workflows):
            workflows[index] = wf
        else:
            workflows.append(wf)

        if isinstance(cfg, dict):
            cfg['workflows'] = workflows
            _save_config(cfg)
        else:
            _save_config(workflows)
        return redirect(url_for("index"))

    # Metodo GET
    if not is_new:
        wf = workflows[index]
    else:
        wf = {"id": "", "trigger": {}, "actions": []}

    return render_template(
        "edit_workflow.html",
        cfg=cfg,
        wf=wf,
        index=index,
        is_new=is_new,
        plugins=plugin_help,
    )


@app.route("/workflow/<int:wf>/trigger", methods=["GET", "POST"])
def edit_trigger_route(wf):
    cfg = load_config(CONFIG_PATH)
    workflows = _get_workflows(cfg)
    if wf >= len(workflows):
        return redirect(url_for("edit_workflow", index=wf))

    if request.method == "POST":
        trigger = {"type": request.form.get("trigger_type")}
        param_keys = [k for k in request.form if k.startswith("param_key_")]
        for key_field in param_keys:
            idx = key_field.rpartition("_")[-1]
            key = request.form.get(f"param_key_{idx}")
            value = request.form.get(f"param_value_{idx}")
            if key:
                trigger[key] = value
        workflows[wf]["trigger"] = trigger
        if isinstance(cfg, dict):
            cfg["workflows"] = workflows
            _save_config(cfg)
        else:
            _save_config(workflows)
        return redirect(url_for("edit_workflow", index=wf))

    trigger = workflows[wf].get("trigger", {})
    return render_template(
        "edit_trigger.html",
        wf_index=wf,
        trigger=trigger,
        triggers=TRIGGERS,
    )


@app.route("/workflow/<int:wf>/action/<int:idx>", methods=["GET", "POST"])
def edit_action_route(wf, idx):
    cfg = load_config(CONFIG_PATH)
    workflows = _get_workflows(cfg)
    if wf >= len(workflows) or idx >= len(workflows[wf].get("actions", [])):
        return redirect(url_for("edit_workflow", index=wf))

    if request.method == "POST":
        action = {"type": request.form.get("action_type"), "params": {}}
        param_keys = [k for k in request.form if k.startswith("param_key_")]
        for key_field in param_keys:
            pidx = key_field.rpartition("_")[-1]
            key = request.form.get(f"param_key_{pidx}")
            value = request.form.get(f"param_value_{pidx}")
            if key:
                action["params"][key] = value
        workflows[wf]["actions"][idx] = action
        if isinstance(cfg, dict):
            cfg["workflows"] = workflows
            _save_config(cfg)
        else:
            _save_config(workflows)
        return redirect(url_for("edit_workflow", index=wf))

    action = workflows[wf]["actions"][idx]
    return render_template(
        "edit_action.html",
        wf_index=wf,
        idx=idx,
        action=action,
        actions=ACTIONS,
    )


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
        _save_config(cfg)
    else:
        _save_config(workflows)
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    app.run(debug=True)