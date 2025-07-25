import json
import urllib.request
import sys
from pathlib import Path

# Ensure project root is on the path for test execution environments
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pyzap.plugins.slack_notify import SlackNotifyAction
from pyzap.plugins.sheets_append import SheetsAppendAction
from pyzap.plugins.gdrive_upload import GDriveUploadAction

class DummyResponse:
    def read(self):
        return b""

def _patch_urlopen(monkeypatch, store):
    def fake(req):
        store['req'] = req
        return DummyResponse()
    monkeypatch.setattr(urllib.request, 'urlopen', fake)


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


def test_slack_notify_error(monkeypatch):
    called = False

    def fake(req):
        nonlocal called
        called = True
        raise urllib.error.URLError("fail")

    monkeypatch.setattr(urllib.request, "urlopen", fake)
    action = SlackNotifyAction({"webhook_url": "http://example.com"})
    # Should not raise
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
    action.execute({})
    assert not called
