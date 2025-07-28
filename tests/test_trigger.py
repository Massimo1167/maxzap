import sys
import types
import imaplib
import os
import pytest
from pathlib import Path

# Ensure project root on path for test imports
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _setup_google(monkeypatch, success=True):
    """Create stub google modules for Gmail trigger tests."""
    google = types.ModuleType("google")
    oauth2 = types.ModuleType("google.oauth2")
    creds_mod = types.ModuleType("google.oauth2.credentials")

    class DummyCreds:
        expired = False
        refresh_token = None

        def refresh(self, request):
            pass

        @staticmethod
        def from_authorized_user_file(path, scopes):
            return DummyCreds()

    creds_mod.Credentials = DummyCreds
    oauth2.credentials = creds_mod
    google.oauth2 = oauth2

    auth = types.ModuleType("google.auth")
    transport = types.ModuleType("google.auth.transport")
    req_mod = types.ModuleType("google.auth.transport.requests")

    class Request:
        pass

    req_mod.Request = Request
    transport.requests = req_mod
    auth.transport = transport
    google.auth = auth

    gapi = types.ModuleType("googleapiclient")
    disc = types.ModuleType("googleapiclient.discovery")

    def fake_build(*args, **kwargs):
        if not success:
            raise RuntimeError("boom")

        class Execute:
            def __init__(self, data):
                self.data = data

            def execute(self):
                return self.data

        class Messages:
            def list(self, userId="me", q=None, maxResults=None):
                return Execute({"messages": [{"id": "1"}]})

            def get(self, userId="me", id=None, format="full"):
                return Execute({"id": id, "snippet": "body"})

        class Users:
            def messages(self):
                return Messages()

        class Service:
            def users(self):
                return Users()

        return Service()

    disc.build = fake_build
    gapi.discovery = disc

    modules = {
        "google": google,
        "google.oauth2": oauth2,
        "google.oauth2.credentials": creds_mod,
        "google.auth": auth,
        "google.auth.transport": transport,
        "google.auth.transport.requests": req_mod,
        "googleapiclient": gapi,
        "googleapiclient.discovery": disc,
    }
    for name, mod in modules.items():
        monkeypatch.setitem(sys.modules, name, mod)


def _setup_openpyxl(monkeypatch):
    """Create a fake openpyxl module for Excel tests."""
    import types
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

    def load_workbook(path):
        wb = Workbook()
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as fh:
                wb.active.rows = json.load(fh)
        return wb

    openpyxl.Workbook = Workbook
    openpyxl.load_workbook = load_workbook
    monkeypatch.setitem(sys.modules, "openpyxl", openpyxl)


def test_gmail_poll_success(monkeypatch):
    _setup_google(monkeypatch, success=True)
    import importlib
    module = importlib.import_module("pyzap.plugins.gmail_poll")
    module = importlib.reload(module)
    GmailPollTrigger = module.GmailPollTrigger

    trigger = GmailPollTrigger({"token_file": "token.json", "query": "test"})
    msgs = trigger.poll()
    assert [m["id"] for m in msgs] == ["1"]


def test_gmail_poll_error(monkeypatch):
    _setup_google(monkeypatch, success=False)
    import importlib
    module = importlib.import_module("pyzap.plugins.gmail_poll")
    module = importlib.reload(module)
    GmailPollTrigger = module.GmailPollTrigger

    trigger = GmailPollTrigger({"token_file": "token.json"})
    assert trigger.poll() == []


def test_gmail_poll_multiple(monkeypatch):
    """Polling multiple Gmail accounts should merge results."""
    _setup_google(monkeypatch, success=True)
    import importlib
    module = importlib.import_module("pyzap.plugins.gmail_poll")
    module = importlib.reload(module)
    GmailPollTrigger = module.GmailPollTrigger

    trigger = GmailPollTrigger(
        {
            "accounts": [
                {"token_file": "a.json", "query": "q1"},
                {"token_file": "b.json", "query": "q2"},
            ]
        }
    )
    msgs = trigger.poll()
    assert len(msgs) == 2
    assert {m["token_file"] for m in msgs} == {"a.json", "b.json"}


def test_imap_poll(monkeypatch):
    from pyzap.plugins.imap_poll import ImapPollTrigger

    class DummyIMAP:
        def __init__(self, host):
            self.host = host

        def login(self, user, pwd):
            pass

        def select(self, mbox):
            pass

        def search(self, charset, query):
            return ("OK", [b"1 2"])

        def fetch(self, num, parts):
            return ("OK", [(b"1", b"Subject: s\r\nFrom: f\r\n\r\nBody")])

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            pass

    monkeypatch.setattr(imaplib, "IMAP4_SSL", lambda host: DummyIMAP(host))
    trigger = ImapPollTrigger({"host": "h", "username": "u", "password": "p"})
    msgs = trigger.poll()
    assert [m["id"] for m in msgs] == ["1", "2"]


def test_imap_poll_missing_config():
    from pyzap.plugins.imap_poll import ImapPollTrigger

    trigger = ImapPollTrigger({})
    assert trigger.poll() == []


def test_excel_poll(monkeypatch, tmp_path):
    _setup_openpyxl(monkeypatch)
    import importlib
    openpyxl = importlib.import_module("openpyxl")
    ExcelPollTrigger = importlib.import_module(
        "pyzap.plugins.excel_poll"
    ).ExcelPollTrigger

    file_path = tmp_path / "book.xlsx"
    state = tmp_path / "state.txt"
    wb = openpyxl.Workbook()
    wb.active.append(["a", "b"])
    wb.save(file_path)

    trigger = ExcelPollTrigger({"file": str(file_path), "state_file": str(state)})
    assert trigger.poll() == []

    wb = openpyxl.load_workbook(file_path)
    wb.active.append([1, 2])
    wb.save(file_path)

    rows = trigger.poll()
    assert rows == [{"id": "2", "values": [1, 2]}]
    assert trigger.poll() == []


def test_excel_poll_filter(monkeypatch, tmp_path):
    _setup_openpyxl(monkeypatch)
    import importlib
    openpyxl = importlib.import_module("openpyxl")
    ExcelPollTrigger = importlib.import_module(
        "pyzap.plugins.excel_poll"
    ).ExcelPollTrigger

    file_path = tmp_path / "book.xlsx"
    wb = openpyxl.Workbook()
    wb.active.append(["h1", "h2"])
    wb.active.append([1, "keep"])
    wb.active.append([2, "skip"])
    wb.save(file_path)

    trigger = ExcelPollTrigger({"file": str(file_path), "filters": {2: "keep"}})
    rows = trigger.poll()
    assert rows == [{"id": "2", "values": [1, "keep"]}]


def test_excel_poll_missing_dependency(monkeypatch):
    import importlib
    import builtins
    monkeypatch.delitem(sys.modules, "openpyxl", raising=False)
    real_import = builtins.__import__

    def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "openpyxl" or name.startswith("openpyxl."):
            raise ImportError("No module named openpyxl")
        return real_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    module = importlib.import_module("pyzap.plugins.excel_poll")
    module = importlib.reload(module)
    ExcelPollTrigger = module.ExcelPollTrigger

    trigger = ExcelPollTrigger({"file": "book.xlsx"})
    with pytest.raises(RuntimeError):
        trigger.poll()
