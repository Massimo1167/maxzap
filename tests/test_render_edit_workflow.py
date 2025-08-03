import sys
from pathlib import Path
from flask import render_template


# Ensure project root on the path for test execution environments
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pyzap.webapp import app


def test_edit_workflow_template_renders_action_params():
    """Render the edit_workflow template with a sample workflow.

    Ensures that the template renders without raising errors and that
    parameter fields for actions are named correctly.
    """
    cfg = {"admin_email": "", "smtp": {}}
    workflow = {
        "id": "wf1",
        "trigger": {"type": "manual"},
        "actions": [
            {"type": "email", "params": {"subject": "Hello"}}
        ],
    }

    with app.test_request_context():
        html = render_template(
            "edit_workflow.html", cfg=cfg, wf=workflow, index=0, is_new=False
        )

    assert 'name="action_0_param_key_0"' in html
    assert 'name="action_0_param_value_0"' in html


def test_edit_workflow_template_renders_without_params():
    """Template renders when actions have no params dictionary."""
    cfg = {"admin_email": "", "smtp": {}}
    workflow = {
        "id": "wf1",
        "trigger": {"type": "manual"},
        "actions": [{"type": "email"}],
    }

    with app.test_request_context():
        html = render_template(
            "edit_workflow.html", cfg=cfg, wf=workflow, index=0, is_new=False
        )

    assert 'name="action_0_param_key_0"' not in html
