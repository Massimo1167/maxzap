import importlib
import pytest

@pytest.fixture
def trigger_module():
    return importlib.import_module('trigger')

def test_trigger_module_loads(trigger_module):
    assert trigger_module.__name__ == 'trigger'
