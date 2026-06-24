import sys, os, json, time, io
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


def _set_paths(monkeypatch, tmp_path):
    monkeypatch.setattr(sf, "CONFIG_PATH", tmp_path / "config.json")
    monkeypatch.setattr(sf, "CACHE_PATH", tmp_path / "cache.json")


def test_main_missing_config_exits_zero(monkeypatch, tmp_path, capsys):
    _set_paths(monkeypatch, tmp_path)
    rc = sf.main()
    out = capsys.readouterr().out.strip()
    assert rc == 0
    assert "missing config" in out


def test_main_renders_normal(monkeypatch, tmp_path, capsys):
    _set_paths(monkeypatch, tmp_path)
    (tmp_path / "config.json").write_text('{"ak":"A","sk":"S"}')

    fake_result = {
        "Status": "Running",
        "QuotaUsage": [
            {"Level": "session", "Percent": 25, "ResetTimestamp": int(time.time()) + 4770},
            {"Level": "weekly",  "Percent": 62, "ResetTimestamp": int(time.time()) + 10524},
            {"Level": "monthly", "Percent": 31, "ResetTimestamp": int(time.time()) + 2256923},
        ],
    }
    monkeypatch.setattr(sf, "fetch_volcengine_ark", lambda config, now: fake_result)

    rc = sf.main()
    out = capsys.readouterr().out
    assert rc == 0
    assert "5h 25%" in out
    assert "W 62%" in out
    assert "M 31%" in out
    assert "↻5h" in out


def test_main_net_error_no_cache(monkeypatch, tmp_path, capsys):
    _set_paths(monkeypatch, tmp_path)
    (tmp_path / "config.json").write_text('{"ak":"A","sk":"S"}')

    def fail(config, now):
        raise sf.FetchError("boom")

    monkeypatch.setattr(sf, "fetch_volcengine_ark", fail)

    rc = sf.main()
    out = capsys.readouterr().out
    assert rc == 0
    assert "net err" in out


def test_main_uncaught_exception_exits_zero(monkeypatch, tmp_path, capsys):
    _set_paths(monkeypatch, tmp_path)
    (tmp_path / "config.json").write_text('{"ak":"A","sk":"S"}')

    def explode(*a, **k):
        raise RuntimeError("kaboom")

    monkeypatch.setattr(sf, "cached_fetch", explode)

    rc = sf.main()
    out = capsys.readouterr().out
    assert rc == 0
    assert "statusfooter:" in out


def test_read_stdin_model_name_ok():
    stream = io.StringIO('{"model": {"id": "glm-5.1", "display_name": "GLM-5.1"}}')
    assert sf.read_stdin_model_name(stream) == "GLM-5.1"


def test_read_stdin_model_name_invalid_json():
    stream = io.StringIO("not json {")
    assert sf.read_stdin_model_name(stream) is None


def test_read_stdin_model_name_missing_field():
    stream = io.StringIO('{"model": {"id": "glm-5.1"}}')
    assert sf.read_stdin_model_name(stream) is None
    stream2 = io.StringIO('{"workspace": "x"}')
    assert sf.read_stdin_model_name(stream2) is None


def test_read_stdin_model_name_empty():
    assert sf.read_stdin_model_name(io.StringIO("")) is None


def test_main_uses_stdin_model_prefix(monkeypatch, tmp_path, capsys):
    _set_paths(monkeypatch, tmp_path)
    (tmp_path / "config.json").write_text('{"ak":"A","sk":"S"}')

    fake_result = {
        "Status": "Running",
        "QuotaUsage": [
            {"Level": "session", "Percent": 25, "ResetTimestamp": int(time.time()) + 4770},
        ],
    }
    monkeypatch.setattr(sf, "fetch_volcengine_ark", lambda config, now: fake_result)
    monkeypatch.setattr(sys, "stdin", io.StringIO(
        '{"model": {"id": "glm-5.1", "display_name": "GLM-5.1"}}'
    ))

    rc = sf.main()
    out = capsys.readouterr().out
    assert rc == 0
    assert out.startswith("GLM-5.1  ")
