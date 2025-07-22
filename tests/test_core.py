import importlib
import pytest

@pytest.fixture
def core_module():
    return importlib.import_module('core')

def test_core_module_loads(core_module):
    assert core_module.__name__ == 'core'
