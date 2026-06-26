import sys, os, time, io, json, pytest
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


class _FakeResponse:
    def __init__(self, status, body):
        self.status = status
        self._body = body.encode() if isinstance(body, str) else body
    def read(self):
        return self._body
    def __enter__(self): return self
    def __exit__(self, *a): pass


def test_fetch_minimax_success(monkeypatch):
    captured = {}

    def fake_urlopen(req, timeout=20):
        captured["url"] = req.full_url
        captured["headers"] = dict(req.headers)
        body = json.dumps({
            "base_resp": {"status_code": 0, "status_msg": "success"},
            "model_remains": [
                {
                    "model_name": "general",
                    "start_time": 1782302400000,
                    "end_time": 1782316800000,
                    "remains_time": 3600000,
                    "current_interval_total_count": 100,
                    "current_interval_usage_count": 32,
                    "current_interval_remaining_percent": 68,
                    "current_interval_status": 1,
                    "current_weekly_total_count": 500,
                    "current_weekly_usage_count": 215,
                    "current_weekly_remaining_percent": 57,
                    "current_weekly_status": 1,
                    "weekly_start_time": 1782057600000,
                    "weekly_end_time": 1782662400000,
                    "weekly_remains_time": 349000000,
                    "weekly_boost_permille": 1500,
                },
                {
                    "model_name": "video",
                    "start_time": 1782302400000,
                    "end_time": 1782316800000,
                    "remains_time": 3600000,
                    "current_interval_total_count": 100,
                    "current_interval_usage_count": 0,
                    "current_interval_remaining_percent": 100,
                    "current_interval_status": 3,
                    "current_weekly_total_count": 500,
                    "current_weekly_usage_count": 0,
                    "current_weekly_remaining_percent": 100,
                    "current_weekly_status": 3,
                    "weekly_start_time": 1782057600000,
                    "weekly_end_time": 1782662400000,
                    "weekly_remains_time": 349000000,
                    "weekly_boost_permille": 1500,
                },
            ],
        })
        return _FakeResponse(200, body)

    monkeypatch.setattr(sf.urllib.request, "urlopen", fake_urlopen)

    now = time.time()
    result = sf.fetch_minimax({"minimax_api_key": "sk-test"}, now)
    assert result["Status"] == "Running"
    assert len(result["QuotaUsage"]) == 2
    # general: 4h + weekly (showing remaining balance, not used)
    assert result["QuotaUsage"][0]["Level"] == "session"
    assert result["QuotaUsage"][0]["Percent"] == 68  # remaining_percent directly
    assert result["QuotaUsage"][1]["Level"] == "weekly"
    assert result["QuotaUsage"][1]["Percent"] == 57  # weekly remaining_percent directly
    # video is filtered out
    assert all(e["Level"] in ("session", "weekly") for e in result["QuotaUsage"])
    # URL and auth header
    assert "minimaxi.com/v1/api/openplatform/coding_plan/remains" in captured["url"]
    assert captured["headers"]["Authorization"] == "Bearer sk-test"


def test_fetch_minimax_api_error(monkeypatch):
    def fake_urlopen(req, timeout=20):
        body = json.dumps({
            "base_resp": {"status_code": 1004, "status_msg": "cookie is missing"}
        })
        return _FakeResponse(200, body)

    monkeypatch.setattr(sf.urllib.request, "urlopen", fake_urlopen)

    with pytest.raises(sf.FetchError, match="MiniMax: cookie is missing"):
        sf.fetch_minimax({"minimax_api_key": "sk-test"}, time.time())


def test_fetch_minimax_network_error(monkeypatch):
    import urllib.error

    def fake_urlopen(req, timeout=20):
        raise urllib.error.URLError("network down")

    monkeypatch.setattr(sf.urllib.request, "urlopen", fake_urlopen)

    with pytest.raises(sf.FetchError):
        sf.fetch_minimax({"minimax_api_key": "sk-test"}, time.time())


def test_fetch_minimax_missing_key():
    with pytest.raises(sf.FetchError, match="missing minimax_api_key"):
        sf.fetch_minimax({}, time.time())


def test_fetch_minimax_no_general_model(monkeypatch):
    def fake_urlopen(req, timeout=20):
        body = json.dumps({
            "base_resp": {"status_code": 0, "status_msg": "success"},
            "model_remains": [
                {"model_name": "video", "current_interval_remaining_percent": 100,
                 "remains_time": 3600000, "current_weekly_remaining_percent": 100,
                 "weekly_remains_time": 349000000},
            ],
        })
        return _FakeResponse(200, body)

    monkeypatch.setattr(sf.urllib.request, "urlopen", fake_urlopen)

    with pytest.raises(sf.FetchError, match="no general model_remains"):
        sf.fetch_minimax({"minimax_api_key": "sk-test"}, time.time())


def test_render_minimax_labels():
    result = {
        "Status": "Running",
        "QuotaUsage": [
            {"Level": "session", "Percent": 68, "ResetTimestamp": int(time.time()) + 3600},
            {"Level": "weekly", "Percent": 57, "ResetTimestamp": int(time.time()) + 349000},
        ],
    }
    now = int(time.time())
    out = sf.render(result, now, stale=False, provider="minimax")
    assert "4h 68% ▓▓▓" in out
    assert "W 57% ▓▓░" in out
    assert "↻4h" in out


def test_render_minimax_color_thresholds():
    """For remaining-balance semantics: low remaining = danger (red/yellow)."""
    result = {
        "Status": "Running",
        "QuotaUsage": [
            {"Level": "session", "Percent": 35, "ResetTimestamp": int(time.time()) + 3600},
            {"Level": "weekly", "Percent": 15, "ResetTimestamp": int(time.time()) + 349000},
        ],
    }
    now = int(time.time())
    out = sf.render(result, now, stale=False, provider="minimax")
    assert "\033[33m4h 35% ▓▓░\033[0m" in out  # yellow (≤40, >20)
    assert "\033[31mW 15% ▓░░\033[0m" in out   # red (≤20)


def test_render_minimax_fallback_to_default_labels():
    """Unknown provider falls back to default 5h/W/M labels."""
    result = {
        "Status": "Running",
        "QuotaUsage": [
            {"Level": "session", "Percent": 50, "ResetTimestamp": int(time.time()) + 3600},
        ],
    }
    now = int(time.time())
    out = sf.render(result, now, stale=False, provider="unknown")
    assert "5h 50% ▓░░" in out


def test_load_config_new_format(tmp_path):
    p = tmp_path / "config.json"
    p.write_text(json.dumps({
        "active": "minimax",
        "cache_ttl": 120,
        "providers": {
            "minimax": {"minimax_api_key": "sk-abc"},
            "volcengine_ark": {"ak": "AK", "sk": "SK"},
        }
    }))
    cfg = sf.load_config(p)
    assert cfg["minimax_api_key"] == "sk-abc"
    assert cfg["cache_ttl"] == 120
    assert cfg["_provider"] == "minimax"


def test_load_config_old_format_backward_compat(tmp_path):
    p = tmp_path / "config.json"
    p.write_text('{"ak":"A","sk":"S","cache_ttl":30}')
    cfg = sf.load_config(p)
    assert cfg["ak"] == "A"
    assert cfg["sk"] == "S"
    assert cfg["cache_ttl"] == 30
    assert cfg["_provider"] == "volcengine_ark"


def test_load_config_new_format_missing_active_provider(tmp_path):
    p = tmp_path / "config.json"
    p.write_text(json.dumps({
        "active": "anthropic",
        "providers": {"minimax": {"minimax_api_key": "sk-abc"}}
    }))
    with pytest.raises(sf.ConfigError, match="no config for active"):
        sf.load_config(p)


def test_main_minimax(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(sf, "CONFIG_PATH", tmp_path / "config.json")
    monkeypatch.setattr(sf, "CACHE_PATH", tmp_path / "cache.json")
    (tmp_path / "config.json").write_text(json.dumps({
        "active": "minimax",
        "providers": {"minimax": {"minimax_api_key": "sk-test"}}
    }))

    now = time.time()
    fake_result = {
        "Status": "Running",
        "QuotaUsage": [
            {"Level": "session", "Percent": 32, "ResetTimestamp": int(now) + 3600},
            {"Level": "weekly", "Percent": 43, "ResetTimestamp": int(now) + 349000},
        ],
    }

    def fake_minimax(config, now):
        assert config["minimax_api_key"] == "sk-test"
        return fake_result

    monkeypatch.setattr(sf, "fetch_minimax", fake_minimax)

    rc = sf.main()
    out = capsys.readouterr().out
    assert rc == 0
    assert "4h 32% ▓░░" in out
    assert "W 43% ▓▓░" in out
    assert "↻4h" in out


def test_main_unknown_provider(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(sf, "CONFIG_PATH", tmp_path / "config.json")
    monkeypatch.setattr(sf, "CACHE_PATH", tmp_path / "cache.json")
    (tmp_path / "config.json").write_text(json.dumps({
        "active": "unknown",
        "providers": {"unknown": {}}
    }))

    rc = sf.main()
    out = capsys.readouterr().out
    assert rc == 0
    assert "unknown provider=unknown" in out
