import os
import sys
import json
import types
import sqlite3
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _setup_openpyxl(monkeypatch):
    import json
    openpyxl = types.ModuleType("openpyxl")

    class DummyCell:
        def __init__(self, value):
            self.value = value

    class Worksheet:
        def __init__(self):
            self.rows = []

        def append(self, values):
            self.rows.append(list(values))

        def __getitem__(self, idx):
            row = self.rows[idx - 1]
            return [DummyCell(v) for v in row]

        def cell(self, row, column, value=None):
            while len(self.rows) < row:
                self.rows.append([])
            r = self.rows[row - 1]
            while len(r) < column:
                r.append(None)
            r[column - 1] = value

    class Workbook:
        def __init__(self):
            self.active = Worksheet()

        def save(self, path):
            with open(path, "w", encoding="utf-8") as fh:
                json.dump(self.active.rows, fh)

        def __getitem__(self, name):
            return self.active

    def load_workbook(path):
        wb = Workbook()
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as fh:
                wb.active.rows = json.load(fh)
        return wb

    openpyxl.Workbook = Workbook
    openpyxl.load_workbook = load_workbook
    monkeypatch.setitem(sys.modules, "openpyxl", openpyxl)



def test_file_create_action(tmp_path):
    from pyzap.plugins.excel_watch import FileCreateAction
    path = tmp_path / "out.json"
    action = FileCreateAction({"path": str(path), "format": "json"})
    action.execute({"a": 1, "b": 2})
    data = json.loads(path.read_text())
    assert data == {"a": 1, "b": 2}


def test_db_save_action(tmp_path):
    from pyzap.plugins.excel_watch import DBSaveAction

    db = tmp_path / "data.db"
    action = DBSaveAction({"db": str(db), "table": "t"})
    action.execute({"a": 1, "b": "x"})
    conn = sqlite3.connect(db)
    rows = list(conn.execute("SELECT a, b FROM t"))
    conn.close()
    assert rows == [(1, "x")]


def test_excel_write_action(monkeypatch, tmp_path):
    _setup_openpyxl(monkeypatch)
    import importlib
    openpyxl = importlib.import_module("openpyxl")
    from pyzap.plugins.excel_watch import ExcelWriteRowAction

    file_path = tmp_path / "book.xlsx"
    wb = openpyxl.Workbook()
    wb.save(file_path)

    action = ExcelWriteRowAction({"file": str(file_path)})
    action.execute({"values": [1, 2]})

    wb2 = openpyxl.load_workbook(file_path)
    assert wb2.active.rows == [[1, 2]]


def test_attachment_download_action(tmp_path):
    src = tmp_path / "a.txt"
    src.write_text("data")
    dest = tmp_path / "dest"
    from pyzap.plugins.excel_watch import AttachmentDownloadAction

    action = AttachmentDownloadAction({"dest": str(dest), "rename": "copy_{filename}"})
    result = action.execute({"attachments": [str(src)], "id": "1"})
    assert result["downloaded"]
    assert (dest / "copy_a.txt").exists()
