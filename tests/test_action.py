import json
import urllib.request
import sys
import imaplib
from pathlib import Path
import pytest

# Ensure project root is on the path for test execution environments
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pyzap.plugins.slack_notify import SlackNotifyAction
from pyzap.plugins.sheets_append import SheetsAppendAction
from pyzap.plugins.gdrive_upload import GDriveUploadAction

class DummyResponse:
    def __init__(self, status: int = 200):
        self._status = status

    def read(self):
        return b""

    def getcode(self):
        return self._status

def _patch_urlopen(monkeypatch, store):
    def fake(req):
        store['req'] = req
        return DummyResponse()
    monkeypatch.setattr(urllib.request, 'urlopen', fake)


def _setup_openpyxl(monkeypatch):
    import types, json, os, sys

    openpyxl = types.ModuleType('openpyxl')

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
            with open(path, 'w', encoding='utf-8') as fh:
                json.dump(self.active.rows, fh)

        def __getitem__(self, name):
            return self.active

    def load_workbook(path):
        wb = Workbook()
        if os.path.exists(path):
            with open(path, 'r', encoding='utf-8') as fh:
                wb.active.rows = json.load(fh)
        return wb

    openpyxl.Workbook = Workbook
    openpyxl.load_workbook = load_workbook
    monkeypatch.setitem(sys.modules, 'openpyxl', openpyxl)


def _setup_gmail(monkeypatch):
    import types, base64, sys

    google = types.ModuleType('google')
    oauth2 = types.ModuleType('google.oauth2')
    creds_mod = types.ModuleType('google.oauth2.credentials')

    class DummyCreds:
        expired = False
        refresh_token = None

        def refresh(self, req):
            pass

        @staticmethod
        def from_authorized_user_file(path, scopes):
            return DummyCreds()

    creds_mod.Credentials = DummyCreds
    oauth2.credentials = creds_mod
    google.oauth2 = oauth2

    auth = types.ModuleType('google.auth')
    transport = types.ModuleType('google.auth.transport')
    req_mod = types.ModuleType('google.auth.transport.requests')

    class Request:
        pass

    req_mod.Request = Request
    transport.requests = req_mod
    auth.transport = transport
    google.auth = auth

    gapi = types.ModuleType('googleapiclient')
    disc = types.ModuleType('googleapiclient.discovery')

    def fake_build(*args, **kwargs):
        class Execute:
            def __init__(self, data):
                self.data = data

            def execute(self):
                return self.data

        class Attachments:
            def get(self, userId="me", messageId=None, id=None):
                data = base64.urlsafe_b64encode(b'file').decode()
                return Execute({"data": data})

        class Messages:
            def get(self, userId="me", id=None, format=None):
                return Execute({
                    "id": id,
                    "snippet": "body",
                    "payload": {
                        "headers": [
                            {"name": "From", "value": "f"},
                            {"name": "Subject", "value": "s"},
                            {"name": "Date", "value": "d"},
                        ],
                        "parts": [
                            {"filename": "a.txt", "body": {"attachmentId": "1"}}
                        ],
                    },
                })

            def attachments(self):
                return Attachments()

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
        'google': google,
        'google.oauth2': oauth2,
        'google.oauth2.credentials': creds_mod,
        'google.auth': auth,
        'google.auth.transport': transport,
        'google.auth.transport.requests': req_mod,
        'googleapiclient': gapi,
        'googleapiclient.discovery': disc,
    }
    for name, mod in modules.items():
        monkeypatch.setitem(sys.modules, name, mod)


def test_slack_notify(monkeypatch):
    store = {}
    _patch_urlopen(monkeypatch, store)
    action = SlackNotifyAction({'webhook_url': 'http://example.com'})
    action.execute({'text': 'hi'})
    req = store['req']
    assert req.full_url == 'http://example.com'
    assert json.loads(req.data.decode()) == {'text': 'hi'}


def test_sheets_append(monkeypatch):
    store = {}
    _patch_urlopen(monkeypatch, store)
    action = SheetsAppendAction({'sheet_id': 'SID', 'range': 'Sheet1!A1', 'token': 'T'})
    action.execute({'values': ['a', 'b']})
    req = store['req']
    assert 'SID' in req.full_url
    assert 'Sheet1%21A1' in req.full_url
    assert req.headers['Authorization'] == 'Bearer T'
    assert json.loads(req.data.decode()) == {'values': [['a', 'b']]}


def test_gdrive_upload(monkeypatch, tmp_path):
    store = {}
    _patch_urlopen(monkeypatch, store)
    file_path = tmp_path / 'f.txt'
    file_path.write_text('hello')
    action = GDriveUploadAction({'folder_id': 'FID', 'token': 'TT'})
    action.execute({'file_path': str(file_path)})
    req = store['req']
    assert 'upload/drive/v3/files' in req.full_url
    assert req.headers['Authorization'] == 'Bearer TT'
    assert b'hello' in req.data


def test_gdrive_upload_status_error(monkeypatch):
    def fake(req):
        return DummyResponse(status=400)

    monkeypatch.setattr(urllib.request, 'urlopen', fake)
    action = GDriveUploadAction({'folder_id': 'FID', 'token': 'TT'})
    with pytest.raises(RuntimeError):
        action.execute({'content': b'data'})


def test_slack_notify_error(monkeypatch):
    called = False

    def fake(req):
        nonlocal called
        called = True
        raise urllib.error.URLError("fail")

    monkeypatch.setattr(urllib.request, "urlopen", fake)
    action = SlackNotifyAction({"webhook_url": "http://example.com"})
    with pytest.raises(RuntimeError):
        action.execute({"text": "hi"})
    assert called


def test_slack_notify_missing(monkeypatch):
    called = False

    def fake(req):
        nonlocal called
        called = True
        return DummyResponse()

    monkeypatch.setattr(urllib.request, "urlopen", fake)
    action = SlackNotifyAction({"webhook_url": ""})
    with pytest.raises(ValueError):
        action.execute({})
    assert not called


def test_gmail_archive(monkeypatch, tmp_path):
    _setup_gmail(monkeypatch)
    import importlib
    module = importlib.import_module('pyzap.plugins.gmail_archive')
    module = importlib.reload(module)
    action_cls = module.GmailArchiveAction
    action = action_cls({'token_file': 'token.json', 'local_dir': str(tmp_path)})
    result = action.execute({'id': '123'})
    folder = tmp_path / '123'
    assert folder.exists()
    assert (folder / 'a.txt').read_bytes() == b'file'
    assert result['sender'] == 'f'


def test_gmail_archive_filtered(monkeypatch, tmp_path):
    _setup_gmail(monkeypatch)
    import importlib
    module = importlib.import_module('pyzap.plugins.gmail_archive')
    module = importlib.reload(module)
    action_cls = module.GmailArchiveAction
    action = action_cls({
        'token_file': 'token.json',
        'local_dir': str(tmp_path),
        'save_message': False,
        'attachment_types': ['.pdf'],
    })
    result = action.execute({'id': '123'})
    folder = tmp_path / '123'
    assert not folder.exists()
    assert result['attachments'] == []
    assert result['storage_path'] == ''


def test_imap_archive(monkeypatch, tmp_path):
    from pyzap.plugins.imap_archive import ImapArchiveAction

    class DummyIMAP:
        def __init__(self, host):
            pass

        def login(self, u, p):
            pass

        def select(self, mbox):
            pass

        def fetch(self, num, parts):
            msg = (
                b"Subject: s\r\nFrom: f\r\nDate: d\r\n"
                b"Content-Type: multipart/mixed; boundary=ab\r\n\r\n"
                b"--ab\r\nContent-Type: text/plain\r\n\r\nbody\r\n"
                b"--ab\r\nContent-Type: text/plain; name=att.txt\r\n"
                b"Content-Disposition: attachment; filename=att.txt\r\n\r\nfile\r\n"
                b"--ab--"
            )
            return ("OK", [(b"1", msg)])

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            pass

    monkeypatch.setattr(imaplib, 'IMAP4_SSL', lambda host: DummyIMAP(host))
    action = ImapArchiveAction({'host': 'h', 'username': 'u', 'password': 'p', 'local_dir': str(tmp_path)})
    result = action.execute({'id': '1'})
    folder = tmp_path / '1'
    assert (folder / 'att.txt').exists()
    assert result['subject'] == 's'


def test_excel_append(monkeypatch, tmp_path):
    _setup_openpyxl(monkeypatch)
    import importlib
    openpyxl = importlib.import_module('openpyxl')
    ExcelAppendAction = importlib.import_module('pyzap.plugins.excel_append').ExcelAppendAction
    file_path = tmp_path / 'book.xlsx'
    wb = openpyxl.Workbook()
    wb.save(file_path)
    action = ExcelAppendAction({'file': str(file_path)})
    action.execute({'a': 1, 'b': 2})
    wb2 = openpyxl.load_workbook(file_path)
    row = [cell.value for cell in wb2.active[1]]
    assert row == [1, 2]


def test_excel_append_list_conversion(monkeypatch, tmp_path):
    """Lists should be converted to comma separated strings."""
    _setup_openpyxl(monkeypatch)
    import importlib
    openpyxl = importlib.import_module('openpyxl')
    ExcelAppendAction = importlib.import_module('pyzap.plugins.excel_append').ExcelAppendAction

    file_path = tmp_path / 'book.xlsx'
    wb = openpyxl.Workbook()
    wb.save(file_path)

    action = ExcelAppendAction({'file': str(file_path)})
    action.execute({'labels': ['A', 'B', 'C']})

    wb2 = openpyxl.load_workbook(file_path)
    row = [cell.value for cell in wb2.active[1]]
    assert row == ['A, B, C']


def test_excel_append_skip_storage(monkeypatch, tmp_path):
    _setup_openpyxl(monkeypatch)
    import importlib
    openpyxl = importlib.import_module('openpyxl')
    ExcelAppendAction = importlib.import_module('pyzap.plugins.excel_append').ExcelAppendAction

    file_path = tmp_path / 'book.xlsx'
    wb = openpyxl.Workbook()
    wb.save(file_path)

    action = ExcelAppendAction({'file': str(file_path), 'fields': ['storage_path', 'subject']})
    action.execute({'storage_path': '', 'subject': 'test'})

    wb2 = openpyxl.load_workbook(file_path)
    row = [cell.value for cell in wb2.active[1]]
    assert row == [None, 'test']


def test_excel_append_missing_dependency(monkeypatch, tmp_path):
    """excel_append should error gracefully when openpyxl is unavailable."""
    import importlib, sys, builtins

    monkeypatch.delitem(sys.modules, 'openpyxl', raising=False)
    real_import = builtins.__import__

    def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == 'openpyxl' or name.startswith('openpyxl.'):
            raise ImportError('No module named openpyxl')
        return real_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, '__import__', fake_import)
    module = importlib.import_module('pyzap.plugins.excel_append')
    module = importlib.reload(module)
    ExcelAppendAction = module.ExcelAppendAction

    action = ExcelAppendAction({'file': str(tmp_path / 'book.xlsx')})
    with pytest.raises(RuntimeError):
        action.execute({'values': [1, 2]})
