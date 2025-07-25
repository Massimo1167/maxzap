"""Configuration management for PyZap."""

import json
import os
import re
from typing import Any, Dict, List, Union

# Try to import dotenv, but don't make it a hard requirement.
# It's useful for loading a .env file during development.
try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

# Regex to find placeholders like ${VAR_NAME}
ENV_VAR_PATTERN = re.compile(r"\$\{(.+?)\}")


def _substitute_env_vars(data: Any) -> Any:
    """Recursively substitute environment variables in config data."""
    if isinstance(data, dict):
        return {k: _substitute_env_vars(v) for k, v in data.items()}
    if isinstance(data, list):
        return [_substitute_env_vars(i) for i in data]
    if isinstance(data, str):

        def replace_match(match: re.Match) -> str:
            var_name = match.group(1)
            value = os.environ.get(var_name)
            if value is None:
                # If the variable is not found, return the original placeholder
                # to make it clear which variable is missing.
                return match.group(0)
            return value

        return ENV_VAR_PATTERN.sub(replace_match, data)
    return data


def load_config(path: str) -> Union[Dict[str, Any], List[Dict[str, Any]]]:
    """Load configuration from JSON file with environment variable substitution."""
    with open(path, "r", encoding="utf-8") as fh:
        raw_config = json.load(fh)
    return _substitute_env_vars(raw_config)


def save_config(path: str, config: Union[Dict[str, Any], List[Dict[str, Any]]]) -> None:
    """Save configuration back to a JSON file."""
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(config, fh, indent=2)
