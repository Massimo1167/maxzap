import importlib
import pytest

@pytest.fixture
def action_module():
    return importlib.import_module('action')

def test_action_module_loads(action_module):
    assert action_module.__name__ == 'action'
