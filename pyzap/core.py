import importlib
import pkgutil
import asyncio
import pathlib
from typing import Dict, Any, List, Callable


class BaseTrigger:
    """Base class for triggers."""

    def poll(self) -> List[Any]:
        """Poll for new items. Should be overridden by subclasses."""
        raise NotImplementedError


class BaseAction:
    """Base class for actions."""

    def run(self, data: Any) -> None:
        """Run the action using provided data."""
        raise NotImplementedError


# TODO: Add OAuth2 helpers for authenticating to services
# TODO: Add deduping of trigger events
# TODO: Add retry logic for failed actions


def load_plugins() -> Dict[str, Any]:
    """Load plugin modules from the ``pyzap.plugins`` package."""
    plugins_pkg = importlib.import_module("pyzap.plugins")
    plugins_path = pathlib.Path(plugins_pkg.__file__).parent
    plugins: Dict[str, Any] = {}
    for module_info in pkgutil.iter_modules([str(plugins_path)]):
        module = importlib.import_module(f"pyzap.plugins.{module_info.name}")
        plugins[module_info.name] = module
    return plugins


async def _execute_workflow(plugin: Any) -> None:
    """Execute workflow for a single plugin."""
    if hasattr(plugin, "run") and callable(plugin.run):
        await asyncio.to_thread(plugin.run)


def run_all_workflows() -> None:
    """Execute all workflows discovered via plugins."""
    plugins = load_plugins()
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    tasks = [loop.create_task(_execute_workflow(plugin)) for plugin in plugins.values()]
    if tasks:
        loop.run_until_complete(asyncio.gather(*tasks))
    loop.close()
