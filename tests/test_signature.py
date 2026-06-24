import sys
from pathlib import Path
import importlib.util
import importlib.machinery

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_loader(
    "statusfooter",
    importlib.machinery.SourceFileLoader("statusfooter", str(ROOT / "statusfooter")),
)
sf = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sf)

import datetime


def test_sign_request_deterministic():
    fixed = datetime.datetime(2026, 6, 14, 21, 4, 36)
    headers = sf.sign_request(
        ak="AK_TEST",
        sk="SK_TEST",
        body='{}',
        now=fixed,
        action="GetCodingPlanUsage",
        version="2024-01-01",
        host="open.volcengineapi.com",
        region="cn-beijing",
        service="ark",
    )
    assert headers["X-Date"] == "20260614T210436Z"
    assert headers["Content-Type"] == "application/json"
    assert headers["Host"] == "open.volcengineapi.com"
    # body hash of "{}"
    assert headers["X-Content-Sha256"] == (
        "44136fa355b3678a1146ad16f7e8649e94fb4fc21fe77e8310c060f61caaff8a"
    )
    auth = headers["Authorization"]
    assert auth.startswith("HMAC-SHA256 Credential=AK_TEST/20260614/cn-beijing/ark/request,")
    assert "SignedHeaders=content-type;host;x-content-sha256;x-date" in auth
    assert "Signature=" in auth
    sig = auth.split("Signature=")[1]
    assert len(sig) == 64
    assert all(c in "0123456789abcdef" for c in sig)


def test_sign_request_different_body_different_sig():
    fixed = datetime.datetime(2026, 6, 14, 21, 4, 36)
    h1 = sf.sign_request("AK", "SK", "{}", fixed,
                         "GetCodingPlanUsage", "2024-01-01",
                         "open.volcengineapi.com", "cn-beijing", "ark")
    h2 = sf.sign_request("AK", "SK", '{"x":1}', fixed,
                         "GetCodingPlanUsage", "2024-01-01",
                         "open.volcengineapi.com", "cn-beijing", "ark")
    assert h1["Authorization"] != h2["Authorization"]
    assert h1["X-Content-Sha256"] != h2["X-Content-Sha256"]


import json
import io


class _FakeResponse:
    def __init__(self, status, body):
        self.status = status
        self._body = body.encode() if isinstance(body, str) else body
    def read(self):
        return self._body
    def __enter__(self): return self
    def __exit__(self, *a): pass


def test_fetch_quota_usage_success(monkeypatch):
    captured = {}

    def fake_urlopen(req, timeout=20):
        captured["url"] = req.full_url
        captured["method"] = req.get_method()
        captured["body"] = req.data
        captured["headers"] = dict(req.headers)
        body = json.dumps({
            "ResponseMetadata": {"RequestId": "x"},
            "Result": {
                "Status": "Running",
                "UpdateTimestamp": 100,
                "QuotaUsage": [
                    {"Level": "session", "Percent": 10, "ResetTimestamp": 200},
                ],
            },
        })
        return _FakeResponse(200, body)

    monkeypatch.setattr(sf.urllib.request, "urlopen", fake_urlopen)

    result = sf.fetch_quota_usage("AK_X", "SK_X")
    assert result["Status"] == "Running"
    assert result["QuotaUsage"][0]["Level"] == "session"
    assert "Action=GetCodingPlanUsage" in captured["url"]
    assert captured["method"] == "POST"
    assert captured["body"] == b"{}"


def test_fetch_quota_usage_http_error(monkeypatch):
    import urllib.error

    def fake_urlopen(req, timeout=20):
        raise urllib.error.HTTPError(req.full_url, 500, "Server Error",
                                     hdrs=None, fp=io.BytesIO(b"oops"))

    monkeypatch.setattr(sf.urllib.request, "urlopen", fake_urlopen)

    import pytest
    with pytest.raises(sf.FetchError):
        sf.fetch_quota_usage("AK", "SK")
