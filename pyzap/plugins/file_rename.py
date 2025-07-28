"""Rename downloaded files using a template."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List

from ..core import BaseAction


class RenameFilesAction(BaseAction):
    """Rename files with a format pattern."""

    def execute(self, data: Dict[str, Any]) -> Dict[str, Any]:
        files: List[str] = data.get("files", [])
        pattern = self.params.get("pattern", "{name}{ext}")
        if not files:
            return data
        renamed: List[str] = []
        for path in files:
            p = Path(path)
            new_name = pattern.format(name=p.stem, ext=p.suffix, **data)
            target = p.with_name(new_name)
            p.rename(target)
            renamed.append(str(target))
        data["files"] = renamed
        return data
