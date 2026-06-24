import sys, os, time, json
from pathlib import Path
import importlib.util
import importlib.machinery
import pytest

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_loader(
    "statusfooter",
    importlib.machinery.SourceFileLoader("statusfooter", str(ROOT / "statusfooter")),
)
sf = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sf)


SAMPLE_RESULT = {
    "Status": "Running",
    "QuotaUsage": [{"Level": "session", "Percent": 10, "ResetTimestamp": 99}],
}


def test_write_then_read_cache(tmp_path):
    p = tmp_path / "cache.json"
    sf.write_cache_atomic(p, SAMPLE_RESULT)
    got = sf.read_cache(p)
    assert got == SAMPLE_RESULT


def test_read_cache_missing(tmp_path):
    p = tmp_path / "missing.json"
    assert sf.read_cache(p) is None


def test_read_cache_corrupt(tmp_path):
    p = tmp_path / "bad.json"
    p.write_text("not json {{{")
    assert sf.read_cache(p) is None


def test_atomic_write_no_partial(tmp_path, monkeypatch):
    p = tmp_path / "cache.json"
    sf.write_cache_atomic(p, SAMPLE_RESULT)
    def fail_replace(*a, **kw):
        raise OSError("disk full")
    monkeypatch.setattr(sf.os, "replace", fail_replace)
    with pytest.raises(OSError):
        sf.write_cache_atomic(p, {"Status": "Other"})
    assert sf.read_cache(p) == SAMPLE_RESULT


def test_cached_fetch_hit(tmp_path, monkeypatch):
    cache_path = tmp_path / "cache.json"
    sf.write_cache_atomic(cache_path, SAMPLE_RESULT)

    def should_not_call(*a, **k):
        raise AssertionError("fetch should not be called on cache hit")

    monkeypatch.setattr(sf, "fetch_volcengine_ark", should_not_call)
    config = {"ak": "AK", "sk": "SK", "cache_ttl": 60}
    result, stale = sf.cached_fetch(config, cache_path, now=time.time())
    assert result == SAMPLE_RESULT
    assert stale is False


def test_cached_fetch_miss_calls_api(tmp_path, monkeypatch):
    cache_path = tmp_path / "cache.json"
    NEW_RESULT = {"Status": "Running", "QuotaUsage": []}

    def fake_fetch(config, now):
        return NEW_RESULT

    monkeypatch.setattr(sf, "fetch_volcengine_ark", fake_fetch)
    config = {"ak": "AK", "sk": "SK", "cache_ttl": 60}
    result, stale = sf.cached_fetch(config, cache_path, now=time.time())
    assert result == NEW_RESULT
    assert stale is False
    assert sf.read_cache(cache_path) == NEW_RESULT


def test_cached_fetch_expired(tmp_path, monkeypatch):
    cache_path = tmp_path / "cache.json"
    sf.write_cache_atomic(cache_path, SAMPLE_RESULT)
    old = time.time() - 3600
    os.utime(cache_path, (old, old))

    NEW_RESULT = {"Status": "Running", "QuotaUsage": []}
    monkeypatch.setattr(sf, "fetch_volcengine_ark", lambda config, now: NEW_RESULT)

    config = {"ak": "AK", "sk": "SK", "cache_ttl": 60}
    result, stale = sf.cached_fetch(config, cache_path, now=time.time())
    assert result == NEW_RESULT
    assert stale is False


def test_cached_fetch_api_fails_uses_stale(tmp_path, monkeypatch):
    cache_path = tmp_path / "cache.json"
    sf.write_cache_atomic(cache_path, SAMPLE_RESULT)
    old = time.time() - 3600
    os.utime(cache_path, (old, old))

    def fail(config, now):
        raise sf.FetchError("network down")

    monkeypatch.setattr(sf, "fetch_volcengine_ark", fail)
    config = {"ak": "AK", "sk": "SK", "cache_ttl": 60}
    result, stale = sf.cached_fetch(config, cache_path, now=time.time())
    assert result == SAMPLE_RESULT
    assert stale is True


def test_cached_fetch_api_fails_no_cache(tmp_path, monkeypatch):
    cache_path = tmp_path / "no_cache.json"

    def fail(config, now):
        raise sf.FetchError("network down")

    monkeypatch.setattr(sf, "fetch_volcengine_ark", fail)
    config = {"ak": "AK", "sk": "SK", "cache_ttl": 60}
    with pytest.raises(sf.FetchError):
        sf.cached_fetch(config, cache_path, now=time.time())


def test_load_config_ok(tmp_path):
    p = tmp_path / "config.json"
    p.write_text('{"ak":"A","sk":"S","cache_ttl":120}')
    cfg = sf.load_config(p)
    assert cfg["ak"] == "A"
    assert cfg["sk"] == "S"
    assert cfg["cache_ttl"] == 120


def test_load_config_default_ttl(tmp_path):
    p = tmp_path / "config.json"
    p.write_text('{"ak":"A","sk":"S"}')
    cfg = sf.load_config(p)
    assert cfg["cache_ttl"] == 60


def test_load_config_missing_file(tmp_path):
    p = tmp_path / "missing.json"
    with pytest.raises(sf.ConfigError):
        sf.load_config(p)


def test_load_config_missing_keys(tmp_path):
    p = tmp_path / "bad.json"
    p.write_text('{"ak":"A"}')
    with pytest.raises(sf.ConfigError):
        sf.load_config(p)


def test_load_config_corrupt(tmp_path):
    p = tmp_path / "bad.json"
    p.write_text("not json")
    with pytest.raises(sf.ConfigError):
        sf.load_config(p)
