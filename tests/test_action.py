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
    def __init__(self, status: int = 200, data: bytes = b""):
        self._status = status
        self._data = data

    def read(self):
        return self._data

    def getcode(self):
        return self._status

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        pass

def _patch_urlopen(monkeypatch, store):
    def fake(req):
        store['req'] = req
        store.setdefault('reqs', []).append(req)
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

    def load_workbook(path, *args, **kwargs):
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
                if id == "1":
                    data = base64.urlsafe_b64encode(b"file").decode()
                else:
                    data = base64.urlsafe_b64encode(
                        b"body http://example.com/file.pdf"
                    ).decode()
                return Execute({"data": data})

        class Messages:
            def get(self, userId="me", id=None, format=None):
                return Execute(
                    {
                        "id": id,
                        "snippet": "ignored",
                        "payload": {
                            "headers": [
                                {"name": "From", "value": "f"},
                                {"name": "Subject", "value": "s"},
                                {"name": "Date", "value": "d"},
                            ],
                            "parts": [
                                {
                                    "mimeType": "text/plain",
                                    "body": {"attachmentId": "2"},
                                },
                                {"filename": "a.txt", "body": {"attachmentId": "1"}},
                            ],
                        },
                    }
                )

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


def _setup_gmail_html(monkeypatch):
    """Setup Gmail mocks returning an HTML body with a link."""
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
                if id == "1":
                    data = base64.urlsafe_b64encode(b"file").decode()
                else:
                    data = base64.urlsafe_b64encode(
                        b"body <a href=\"http://example.com/download\">link</a>"
                    ).decode()
                return Execute({"data": data})

        class Messages:
            def get(self, userId="me", id=None, format=None):
                return Execute(
                    {
                        "id": id,
                        "snippet": "ignored",
                        "payload": {
                            "headers": [
                                {"name": "From", "value": "f"},
                                {"name": "Subject", "value": "s"},
                                {"name": "Date", "value": "d"},
                            ],
                            "parts": [
                                {
                                    "mimeType": "text/html",
                                    "body": {"attachmentId": "2"},
                                },
                                {"filename": "a.txt", "body": {"attachmentId": "1"}},
                            ],
                        },
                    }
                )

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
    def fake(req):
        store.setdefault('reqs', []).append(req)
        if req.data is None:
            return DummyResponse(data=json.dumps({'values': []}).encode())
        store['req'] = req
        return DummyResponse()

    monkeypatch.setattr(urllib.request, 'urlopen', fake)
    action = SheetsAppendAction({'sheet_id': 'SID', 'range': 'Sheet1!A1', 'token': 'T'})
    action.execute({'values': ['a', 'b']})
    req = store['req']
    assert 'SID' in req.full_url
    assert 'Sheet1%21A1' in req.full_url
    assert req.headers['Authorization'] == 'Bearer T'
    assert json.loads(req.data.decode()) == {'values': [['a', 'b']]}
    assert len(store['reqs']) == 2


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
    assert result['attachment_paths'] == [str(folder / 'a.txt')]


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
    assert result['attachment_paths'] == []
    assert result['storage_path'] == ''


def test_gmail_archive_skip_attachments(monkeypatch, tmp_path):
    _setup_gmail(monkeypatch)
    import importlib
    module = importlib.import_module('pyzap.plugins.gmail_archive')
    module = importlib.reload(module)
    action_cls = module.GmailArchiveAction
    action = action_cls({
        'token_file': 'token.json',
        'local_dir': str(tmp_path),
        'save_attachments': False,
    })
    result = action.execute({'id': '123'})
    folder = tmp_path / '123'
    assert folder.exists()
    assert not (folder / 'a.txt').exists()
    assert result['attachments'] == []
    assert result['attachment_paths'] == []


def test_gmail_archive_links(monkeypatch, tmp_path):
    _setup_gmail(monkeypatch)
    import importlib
    module = importlib.import_module('pyzap.plugins.gmail_archive')
    module = importlib.reload(module)
    action_cls = module.GmailArchiveAction

    class DummyLinkResponse:
        def read(self):
            return b'linked'

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            pass

    def fake_urlopen(req):
        return DummyLinkResponse()

    monkeypatch.setattr(urllib.request, 'urlopen', fake_urlopen)
    action = action_cls({
        'token_file': 'token.json',
        'local_dir': str(tmp_path),
        'download_links': True,
        'attachment_types': ['.pdf'],
    })
    result = action.execute({'id': '123'})
    folder = tmp_path / '123'
    assert folder.exists()
    assert (folder / 'message.txt').read_text() == 'body http://example.com/file.pdf'
    assert (folder / 'file.pdf').read_bytes() == b'linked'
    assert 'file.pdf' in result['attachments']
    assert result['attachment_paths'] == [str(folder / 'file.pdf')]


def test_gmail_archive_links_no_attachments(monkeypatch, tmp_path):
    _setup_gmail(monkeypatch)
    import importlib
    module = importlib.import_module('pyzap.plugins.gmail_archive')
    module = importlib.reload(module)
    action_cls = module.GmailArchiveAction

    class DummyLinkResponse:
        def read(self):
            return b'linked'

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            pass

    monkeypatch.setattr(urllib.request, 'urlopen', lambda req: DummyLinkResponse())
    action = action_cls({
        'token_file': 'token.json',
        'local_dir': str(tmp_path),
        'save_attachments': False,
        'download_links': True,
        'attachment_types': ['.pdf'],
    })
    result = action.execute({'id': '123'})
    folder = tmp_path / '123'
    assert folder.exists()
    assert (folder / 'file.pdf').read_bytes() == b'linked'
    assert result['attachments'] == ['file.pdf']
    assert result['attachment_paths'] == [str(folder / 'file.pdf')]


def test_gmail_archive_token_from_message(monkeypatch, tmp_path):
    """token_file may be supplied in the message payload."""
    _setup_gmail(monkeypatch)
    import importlib
    module = importlib.import_module('pyzap.plugins.gmail_archive')
    module = importlib.reload(module)
    action_cls = module.GmailArchiveAction
    action = action_cls({'local_dir': str(tmp_path)})
    result = action.execute({'id': '123', 'token_file': 'token.json'})
    folder = tmp_path / '123'
    assert folder.exists()
    assert result['sender'] == 'f'
    assert result['attachment_paths'] == [str(folder / 'a.txt')]


def test_gmail_archive_html_link_header(monkeypatch, tmp_path):
    _setup_gmail_html(monkeypatch)
    import importlib
    module = importlib.import_module('pyzap.plugins.gmail_archive')
    module = importlib.reload(module)
    action_cls = module.GmailArchiveAction

    class DummyLinkResponse:
        def __init__(self):
            self.headers = {
                'Content-Disposition': 'attachment; filename="file.pdf"'
            }

        def read(self):
            return b'linked'

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            pass

    monkeypatch.setattr(urllib.request, 'urlopen', lambda req: DummyLinkResponse())
    action = action_cls({
        'token_file': 'token.json',
        'local_dir': str(tmp_path),
        'save_attachments': False,
        'download_links': True,
        'attachment_types': ['.pdf'],
    })
    result = action.execute({'id': '123'})
    folder = tmp_path / '123'
    assert folder.exists()
    assert (folder / 'file.pdf').read_bytes() == b'linked'
    assert result['attachments'] == ['file.pdf']


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


def test_imap_archive_skip_attachments(monkeypatch, tmp_path):
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
    action = ImapArchiveAction({'host': 'h', 'username': 'u', 'password': 'p', 'local_dir': str(tmp_path), 'save_attachments': False})
    result = action.execute({'id': '1'})
    folder = tmp_path / '1'
    assert not (folder / 'att.txt').exists()
    assert result['attachments'] == []


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


def test_sheets_append_skip_duplicate(monkeypatch):
    store = {}

    def fake(req):
        store.setdefault('reqs', []).append(req)
        if req.data is None:
            return DummyResponse(data=json.dumps({'values': [['x', 'y']]}).encode())
        store['req'] = req
        pytest.fail('Should not append when row already exists')

    monkeypatch.setattr(urllib.request, 'urlopen', fake)
    action = SheetsAppendAction({'sheet_id': 'SID', 'range': 'Sheet1!A1', 'token': 'T'})
    action.execute({'values': ['x', 'y']})
    assert len(store['reqs']) == 1


def test_excel_append_skip_duplicate(monkeypatch, tmp_path):
    _setup_openpyxl(monkeypatch)
    import importlib
    openpyxl = importlib.import_module('openpyxl')
    ExcelAppendAction = importlib.import_module('pyzap.plugins.excel_append').ExcelAppendAction

    file_path = tmp_path / 'book.xlsx'
    wb = openpyxl.Workbook()
    wb.save(file_path)

    action = ExcelAppendAction({'file': str(file_path)})
    action.execute({'a': 1, 'b': 2})
    action.execute({'a': 1, 'b': 2})

    wb2 = openpyxl.load_workbook(file_path)
    assert wb2.active.rows == [[1, 2]]


def test_excel_append_attachments_semicolon(monkeypatch, tmp_path):
    _setup_openpyxl(monkeypatch)
    import importlib
    openpyxl = importlib.import_module('openpyxl')
    ExcelAppendAction = importlib.import_module('pyzap.plugins.excel_append').ExcelAppendAction

    file_path = tmp_path / 'book.xlsx'
    wb = openpyxl.Workbook()
    wb.save(file_path)

    action = ExcelAppendAction({'file': str(file_path)})
    action.execute({'attachments': ['a.txt', 'b.txt']})

    wb2 = openpyxl.load_workbook(file_path)
    row = [cell.value for cell in wb2.active[1]]
    assert row == ['a.txt; b.txt']


def test_excel_append_datetime_format(monkeypatch, tmp_path):
    _setup_openpyxl(monkeypatch)
    import importlib
    openpyxl = importlib.import_module('openpyxl')
    ExcelAppendAction = importlib.import_module('pyzap.plugins.excel_append').ExcelAppendAction

    file_path = tmp_path / 'book.xlsx'
    wb = openpyxl.Workbook()
    wb.save(file_path)

    action = ExcelAppendAction({'file': str(file_path)})
    action.execute({'datetime': 'Sat, 26 Jul 2025 04:23:18 +0000 (GMT)'})

    wb2 = openpyxl.load_workbook(file_path)
    row = [cell.value for cell in wb2.active[1]]
    assert row == ['26/07/2025 04:23:18']


def test_excel_append_message_truncate(monkeypatch, tmp_path):
    _setup_openpyxl(monkeypatch)
    import importlib
    openpyxl = importlib.import_module('openpyxl')
    ExcelAppendAction = importlib.import_module('pyzap.plugins.excel_append').ExcelAppendAction

    file_path = tmp_path / 'book.xlsx'
    wb = openpyxl.Workbook()
    wb.save(file_path)

    action = ExcelAppendAction({'file': str(file_path), 'max_message_length': 5})
    action.execute({'summary': 'Hello world'})

    wb2 = openpyxl.load_workbook(file_path)
    row = [cell.value for cell in wb2.active[1]]
    assert row == ['Hello']


def test_excel_append_macro(monkeypatch, tmp_path):
    _setup_openpyxl(monkeypatch)
    import importlib
    openpyxl = importlib.import_module('openpyxl')

    calls = {}
    orig_load = openpyxl.load_workbook

    def fake_load_workbook(path, *args, **kwargs):
        calls['keep_vba'] = kwargs.get('keep_vba')
        return orig_load(path, *args, **kwargs)

    monkeypatch.setattr(openpyxl, 'load_workbook', fake_load_workbook)
    ExcelAppendAction = importlib.import_module('pyzap.plugins.excel_append').ExcelAppendAction

    file_path = tmp_path / 'book.xlsm'
    wb = openpyxl.Workbook()
    wb.save(file_path)

    action = ExcelAppendAction({'file': str(file_path)})
    action.execute({'a': 1})

    assert calls.get('keep_vba') is True


def _setup_pypdf(monkeypatch, texts=None):
    import types, sys

    pypdf = types.ModuleType('PyPDF2')

    class Page:
        def __init__(self, text):
            self._text = text

        def extract_text(self):
            return self._text

    class Reader:
        def __init__(self, path):
            default_texts = ['start invoice 1', 'start invoice 2']
            self.pages = [Page(t) for t in (texts or default_texts)]

    class Writer:
        def __init__(self):
            self.pages = []

        def add_page(self, page):
            self.pages.append(page)

        def write(self, fh):
            fh.write(b'pdf')

    pypdf.PdfReader = Reader
    pypdf.PdfWriter = Writer
    monkeypatch.setitem(sys.modules, 'PyPDF2', pypdf)


def test_pdf_split(monkeypatch, tmp_path):
    _setup_pypdf(monkeypatch)
    import importlib

    module = importlib.import_module('pyzap.plugins.pdf_split')
    module = importlib.reload(module)
    action_cls = module.PDFSplitAction

    src = tmp_path / 'src.pdf'
    src.write_bytes(b'data')

    out_dir = tmp_path / 'out'
    action = action_cls({'output_dir': str(out_dir), 'pattern': 'start', 'name_template': 'file_{index}.pdf'})
    result = action.execute({'pdf_path': str(src)})

    files = sorted(out_dir.glob('*.pdf'))
    assert len(files) == 2
    assert result['files'] == [str(f) for f in files]


def test_pdf_split_missing_fields(monkeypatch, tmp_path):
    _setup_pypdf(monkeypatch)
    import importlib

    module = importlib.import_module('pyzap.plugins.pdf_split')
    module = importlib.reload(module)
    action_cls = module.PDFSplitAction

    src = tmp_path / 'src.pdf'
    src.write_bytes(b'data')

    out_dir = tmp_path / 'out'
    action = action_cls({'output_dir': str(out_dir), 'pattern': 'start', 'name_template': '{missing}_{index}.pdf'})
    result = action.execute({'pdf_path': str(src)})

    files = sorted(out_dir.glob('*.pdf'))
    assert len(files) == 2
    assert [f.name for f in files] == ['_1.pdf', '_2.pdf']
    assert result['files'] == [str(f) for f in files]


def test_pdf_split_regex_fields(monkeypatch, tmp_path):
    texts = [
        'start Numero\n documento V2-\n250035405 Data\n documento 01/01/2023 Denominazione: ACME'
    ]
    _setup_pypdf(monkeypatch, texts=texts)
    import importlib

    module = importlib.import_module('pyzap.plugins.pdf_split')
    module = importlib.reload(module)
    action_cls = module.PDFSplitAction

    src = tmp_path / 'src.pdf'
    src.write_bytes(b'data')

    out_dir = tmp_path / 'out'
    regex_fields = {
        'denominazione': r'Denominazione:\s*(.+)',
        'numero_documento': r'Numero\s+documento\s*(\S+(?:\s*\n\s*\S+)*)',
        'data_documento': r'Data\s+documento\s*(\d{2}/\d{2}/\d{4})',
    }
    action = action_cls(
        {
            'output_dir': str(out_dir),
            'pattern': 'start',
            'name_template': '{numero_documento}.pdf',
            'regex_fields': regex_fields,
        }
    )
    result = action.execute({'pdf_path': str(src)})

    files = sorted(out_dir.glob('*.pdf'))
    assert len(files) == 1
    assert files[0].name == 'V2- 250035405.pdf'
    assert result['records'][0]['numero_documento'] == 'V2- 250035405'
    assert result['records'][0]['data_documento'] == '01/01/2023'
