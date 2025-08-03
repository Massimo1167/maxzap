import json
import inspect
import re

from flask import (
    Flask,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from flask_wtf import CSRFProtect

from .core import ACTIONS, TRIGGERS, load_plugins

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

DEFAULT_CONFIG_PATH = "azienda.agricola-splitpdf.json"


def get_config_path():
    return session.get("config_path", DEFAULT_CONFIG_PATH)


def set_config_path(path: str) -> None:
    session["config_path"] = path

def _get_workflows(cfg):
    """Estrae la lista di workflow dalla configurazione caricata."""
    return cfg.get("workflows", []) if isinstance(cfg, dict) else cfg

def _save_config(cfg, path):
    """Salva l'intera configurazione su ``path``."""
    save_config(path, cfg)


def _parse_param_doc(doc: str):
    """Extract parameter definitions from docstring bullet lists."""
    params = []
    if not doc:
        return params
    section_re = re.compile(
        r"Expected (?:params|parameters|configuration keys|options)", re.I
    )
    in_section = False
    for line in doc.splitlines():
        stripped = line.strip()
        if section_re.search(stripped):
            in_section = True
            continue
        if in_section:
            if not stripped:
                if params:
                    break
                continue
            if not stripped.startswith("-"):
                break
            match = re.match(r"-\s+`+([^`]+)`+(?:\s*\((optional)\))?", stripped)
            if match:
                name = match.group(1)
                optional = bool(match.group(2)) or "optional" in stripped.lower()
                params.append({"name": name, "required": not optional})
    return params


def _get_plugin_params(cls, *, is_trigger: bool):
    """Return parameter info for trigger or action plugin class."""
    funcs = [cls.__init__] if is_trigger else []
    if is_trigger:
        funcs.append(cls.poll)
    else:
        funcs.append(cls.execute)
    params = []
    existing = set()
    for func in funcs:
        sig = inspect.signature(func)
        skip = {"self", "config"} if func is cls.__init__ else {"self", "data"}
        for name, param in sig.parameters.items():
            if name in skip or name in existing:
                continue
            params.append({"name": name, "required": param.default is inspect._empty})
            existing.add(name)
        for p in _parse_param_doc(func.__doc__ or ""):
            if p["name"] not in existing:
                params.append(p)
                existing.add(p["name"])
    if not params:
        for p in _extract_params(cls, is_trigger):
            name = p["name"]
            if name not in existing:
                params.append({"name": name, "required": False})
                existing.add(name)
    return params


@app.route("/help/plugins")
def help_plugins():
    info = get_plugins_metadata()
    return render_template("help_plugins.html", **info)


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


def get_plugins_metadata():
    """Return metadata (docstring and params) for all trigger and action plugins."""
    load_plugins()

    def collect(registry, is_trigger):
        items = []
        for name, cls in sorted(registry.items()):
            items.append(
                {
                    "name": name,
                    "doc": cls.__doc__ or "",
                    "params": _extract_params(cls, is_trigger),
                }
            )
        return items

    return {
        "triggers": collect(TRIGGERS, True),
        "actions": collect(ACTIONS, False),
    }


@app.route("/")
def index():
    cfg = load_config(get_config_path())
    workflows = _get_workflows(cfg)
    return render_template("index.html", cfg=cfg, workflows=workflows)


@csrf.exempt
@app.route("/config/upload", methods=["GET", "POST"])
def upload_config():
    if request.method == "POST":
        file = request.files.get("config_file")
        if not file:
            return render_template("upload_config.html", error="File mancante")
        try:
            data = json.load(file)
        except json.JSONDecodeError:
            return render_template("upload_config.html", error="Invalid JSON")
        path = get_config_path()
        save_config(path, data)
        set_config_path(path)
        return redirect(url_for("index"))
    return render_template("upload_config.html")


@csrf.exempt
@app.route("/config/save", methods=["POST"])
def config_save():
    if request.is_json:
        payload = request.get_json()
        cfg = payload.get("config", {})
        new_path = payload.get("new_path")
    else:
        cfg_str = request.form.get("config", "{}")
        new_path = request.form.get("new_path")
        try:
            cfg = json.loads(cfg_str)
        except json.JSONDecodeError:
            return jsonify({"error": "Invalid JSON"}), 400
    path = new_path or get_config_path()
    _save_config(cfg, path)
    if new_path:
        set_config_path(path)
    return jsonify({"status": "ok", "path": path})


@app.route("/workflow/new", methods=["GET", "POST"])
@app.route("/workflow/<int:index>", methods=["GET", "POST"])
def edit_workflow(index=None):
    path = get_config_path()
    cfg = load_config(path)
    workflows = _get_workflows(cfg)
    is_new = index is None or index >= len(workflows)

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

        if request.form.get("trigger"):
            try:
                wf["trigger"] = json.loads(request.form["trigger"])
            except json.JSONDecodeError:
                return render_template(
                    "edit_workflow.html",
                    cfg=cfg,
                    wf=wf,
                    index=index,
                    is_new=is_new,
                    error="Invalid JSON",
                )
        else:
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

        save_path = request.form.get("new_path") or path
        if isinstance(cfg, dict):
            cfg['workflows'] = workflows
            _save_config(cfg, save_path)
        else:
            _save_config(workflows, save_path)
        if request.form.get("new_path"):
            set_config_path(save_path)

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
    )


@app.route("/workflow/<int:wf>/trigger", methods=["GET", "POST"])
def edit_trigger_route(wf):
    path = get_config_path()
    cfg = load_config(path)
    workflows = _get_workflows(cfg)
    if wf >= len(workflows):
        return redirect(url_for("edit_workflow", index=wf))

    if request.method == "POST":
        trig_type = request.form.get("trigger_type")
        trigger = {"type": trig_type}
        cls = TRIGGERS.get(trig_type)
        if cls:
            for param in _get_plugin_params(cls, is_trigger=True):
                value = request.form.get(param["name"])
                if value:
                    trigger[param["name"]] = value
        workflows[wf]["trigger"] = trigger
        if isinstance(cfg, dict):
            cfg["workflows"] = workflows
            _save_config(cfg, path)
        else:
            _save_config(workflows, path)
        return redirect(url_for("edit_workflow", index=wf))

    trigger_cfg = workflows[wf].get("trigger", {})
    selected_type = request.args.get("trigger_type") or trigger_cfg.get("type")
    params = []
    values = {}
    if selected_type and selected_type in TRIGGERS:
        params = _get_plugin_params(TRIGGERS[selected_type], is_trigger=True)
        if trigger_cfg.get("type") == selected_type:
            values = {k: v for k, v in trigger_cfg.items() if k != "type"}
    return render_template(
        "edit_trigger.html",
        wf_index=wf,
        triggers=TRIGGERS,
        trigger_type=selected_type,
        params=params,
        values=values,
    )


@app.route("/workflow/<int:wf>/action/<int:idx>", methods=["GET", "POST"])
def edit_action_route(wf, idx):
    path = get_config_path()
    cfg = load_config(path)
    workflows = _get_workflows(cfg)
    if wf >= len(workflows) or idx >= len(workflows[wf].get("actions", [])):
        return redirect(url_for("edit_workflow", index=wf))

    if request.method == "POST":
        action_type = request.form.get("action_type")
        action = {"type": action_type, "params": {}}
        cls = ACTIONS.get(action_type)
        if cls:
            for param in _get_plugin_params(cls, is_trigger=False):
                value = request.form.get(param["name"])
                if value:
                    action["params"][param["name"]] = value
        workflows[wf]["actions"][idx] = action
        if isinstance(cfg, dict):
            cfg["workflows"] = workflows
            _save_config(cfg, path)
        else:
            _save_config(workflows, path)
        return redirect(url_for("edit_workflow", index=wf))

    action_cfg = workflows[wf]["actions"][idx]
    selected_type = request.args.get("action_type") or action_cfg.get("type")
    params = []
    values = {}
    if selected_type and selected_type in ACTIONS:
        params = _get_plugin_params(ACTIONS[selected_type], is_trigger=False)
        if action_cfg.get("type") == selected_type:
            values = action_cfg.get("params", {})
    return render_template(
        "edit_action.html",
        wf_index=wf,
        idx=idx,
        actions=ACTIONS,
        action_type=selected_type,
        params=params,
        values=values,
    )


@csrf.exempt
@app.route("/api/workflows", methods=["POST"])
def create_workflow_api():
    """Endpoint API legacy per test o script."""
    data = request.get_json()
    path = get_config_path()
    cfg = load_config(path)
    workflows = _get_workflows(cfg)
    workflows.append(data)
    if isinstance(cfg, dict):
        cfg['workflows'] = workflows
        _save_config(cfg, path)
    else:
        _save_config(workflows, path)

    return jsonify({"status": "ok"})


if __name__ == "__main__":
    app.run(debug=True)
