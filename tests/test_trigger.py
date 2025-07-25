import sys
import types
import imaplib
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
            def list(self, userId="me", q=None):
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
