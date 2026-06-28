import types
import pytest
from googleapiclient.errors import HttpError
from pipeline import upload_youtube as up
from pipeline.errors import UploadError


def _http_error(status):
    resp = types.SimpleNamespace(status=status, reason="err")
    return HttpError(resp, b"{}")


class _Req:
    """Fake resumable request: raises `fails` transient errors, then succeeds."""
    def __init__(self, fails, status=503, final=None):
        self.calls = 0
        self.fails = fails
        self.status = status
        self.final = final if final is not None else {"id": "vid123"}

    def next_chunk(self):
        if self.calls < self.fails:
            self.calls += 1
            raise _http_error(self.status)
        return (None, self.final)


def test_resumable_insert_retries_then_succeeds(monkeypatch):
    monkeypatch.setattr(up.time, "sleep", lambda *_: None)
    resp = up._resumable_insert(_Req(fails=2))
    assert resp["id"] == "vid123"


def test_resumable_insert_raises_after_max(monkeypatch):
    monkeypatch.setattr(up.time, "sleep", lambda *_: None)
    with pytest.raises(UploadError):
        up._resumable_insert(_Req(fails=99))


def test_non_retriable_status_raises(monkeypatch):
    monkeypatch.setattr(up.time, "sleep", lambda *_: None)
    with pytest.raises(UploadError):
        up._resumable_insert(_Req(fails=1, status=400))
