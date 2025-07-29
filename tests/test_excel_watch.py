import os
import sys
import json
import types
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

    class Workbook:
        def __init__(self):
            self.active = Worksheet()

        def save(self, path):
            with open(path, "w", encoding="utf-8") as fh:
                json.dump(self.active.rows, fh)

        def __getitem__(self, name):
            return self.active

    def load_workbook(path, *args, **kwargs):
        wb = Workbook()
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as fh:
                wb.active.rows = json.load(fh)
        return wb

    openpyxl.Workbook = Workbook
    openpyxl.load_workbook = load_workbook
    monkeypatch.setitem(sys.modules, "openpyxl", openpyxl)




def test_excel_row_added_regex(monkeypatch, tmp_path):
    _setup_openpyxl(monkeypatch)
    import importlib
    openpyxl = importlib.import_module("openpyxl")
    module = importlib.import_module("pyzap.plugins.excel_watch")
    ExcelRowAddedTrigger = module.ExcelRowAddedTrigger

    file_path = tmp_path / "book.xlsx"
    state = tmp_path / "state.txt"
    wb = openpyxl.Workbook()
    wb.active.append(["h1", "h2"])
    wb.active.append(["x", "Apple"])
    wb.active.append(["y", "Banana"])
    wb.save(file_path)

    trigger = ExcelRowAddedTrigger(
        {
            "file": str(file_path),
            "state_file": str(state),
            "filters": {2: {"regex": "^A"}},
        }
    )
    rows = trigger.poll()
    assert rows == [{"id": "2", "values": ["x", "Apple"]}]
    assert trigger.poll() == []


def test_excel_cell_change(monkeypatch, tmp_path):
    _setup_openpyxl(monkeypatch)
    import importlib
    openpyxl = importlib.import_module("openpyxl")
    module = importlib.import_module("pyzap.plugins.excel_watch")
    ExcelCellChangeTrigger = module.ExcelCellChangeTrigger

    file_path = tmp_path / "book.xlsx"
    state = tmp_path / "state.json"
    wb = openpyxl.Workbook()
    wb.active.append(["h1", "h2"])
    wb.active.append([1, "old"])
    wb.save(file_path)

    trigger = ExcelCellChangeTrigger(
        {
            "file": str(file_path),
            "state_file": str(state),
            "columns": [2],
        }
    )
    assert trigger.poll() == []

    wb = openpyxl.load_workbook(file_path)
    wb.active.rows[1][1] = "new"
    wb.save(file_path)

    changed = trigger.poll()
    assert changed == [{"id": "2", "values": [1, "new"]}]


def test_excel_file_updated(monkeypatch, tmp_path):
    file_path = tmp_path / "file.xlsx"
    file_path.write_text("data")
    state = tmp_path / "state.txt"
    from pyzap.plugins.excel_watch import ExcelFileUpdatedTrigger

    trigger = ExcelFileUpdatedTrigger({"file": str(file_path), "state_file": str(state)})
    rows = trigger.poll()
    assert rows
    assert trigger.poll() == []
    import time
    time.sleep(1)
    file_path.write_text("new")
    rows = trigger.poll()
    assert rows


def test_excel_attachment_trigger(monkeypatch, tmp_path):
    _setup_openpyxl(monkeypatch)
    import importlib
    openpyxl = importlib.import_module("openpyxl")
    module = importlib.import_module("pyzap.plugins.excel_watch")
    ExcelAttachmentRowTrigger = module.ExcelAttachmentRowTrigger

    file_path = tmp_path / "book.xlsx"
    state = tmp_path / "state.txt"
    wb = openpyxl.Workbook()
    wb.active.append(["h1", "h2", "att"])
    wb.active.append([1, "x", "a.txt b.txt"])
    wb.save(file_path)

    trigger = ExcelAttachmentRowTrigger(
        {
            "file": str(file_path),
            "state_file": str(state),
            "attachment_column": 3,
        }
    )
    rows = trigger.poll()
    assert rows[0]["attachments"] == ["a.txt", "b.txt"]
