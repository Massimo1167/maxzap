"""Store payload in a SQLite table."""

from __future__ import annotations

import json
import sqlite3
from typing import Any, Dict

from ..core import BaseAction


class SqlStoreAction(BaseAction):
    """Save data as JSON in a SQLite database."""

    def execute(self, data: Dict[str, Any]) -> None:
        db = self.params.get("db", "data.db")
        table = self.params.get("table", "records")
        conn = sqlite3.connect(db)
        conn.execute(f"CREATE TABLE IF NOT EXISTS {table} (data TEXT)")
        conn.execute(f"INSERT INTO {table} (data) VALUES (?)", [json.dumps(data)])
        conn.commit()
        conn.close()
