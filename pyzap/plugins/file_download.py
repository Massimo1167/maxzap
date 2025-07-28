"""Download or copy files from provided references."""

from __future__ import annotations

import os
import shutil
from pathlib import Path
from urllib import request
from urllib.parse import urlparse
from typing import Any, Dict, List

from ..core import BaseAction


class DownloadFilesAction(BaseAction):
    """Download attachments specified in ``attachments`` list."""

    def execute(self, data: Dict[str, Any]) -> Dict[str, Any]:
        dest = self.params.get("dest")
        refs: List[str] = data.get("attachments", [])
        if not dest or not refs:
            return data
        Path(dest).mkdir(parents=True, exist_ok=True)
        saved: List[str] = []
        for ref in refs:
            name = os.path.basename(urlparse(ref).path)
            target = Path(dest) / name
            if ref.startswith("http://") or ref.startswith("https://"):
                with request.urlopen(ref) as resp:
                    target.write_bytes(resp.read())
            else:
                shutil.copy(ref, target)
            saved.append(str(target))
        data["files"] = saved
        return data
