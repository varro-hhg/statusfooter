# statusfooter Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build `statusfooter` — a single-file Python script that Claude Code's `statusLine` calls to render Volcengine Ark Coding Plan 5h/weekly/monthly quota usage as a compact, colored, countdown-annotated single line at the bottom of the terminal.

**Architecture:** One executable Python script (`statusfooter`) using only the standard library. Reads AK/SK from `~/.config/statusfooter/config.json`, calls `GetCodingPlanUsage` via Volcengine V4 signing, caches the response in `~/.cache/statusfooter/usage.json` for 60 seconds, and renders an ANSI-colored single-line summary. All errors are caught and degraded to a short stdout label; the script always exits 0.

**Tech Stack:** Python 3.12 stdlib only (`hmac`, `hashlib`, `json`, `urllib`, `datetime`, `pathlib`, `os`, `sys`, `tempfile`, `time`). pytest for tests.

**Spec:** `docs/superpowers/specs/2026-06-14-statusfooter-design.md`

---

## File Structure

```
statusfooter/
├── statusfooter              # Executable single-file script (#!/usr/bin/env python3)
├── install.sh                # Idempotent installer
├── README.md                 # Usage + Claude Code wiring instructions
├── .gitignore                # Ignore __pycache__, .pytest_cache, etc.
├── tests/
│   ├── conftest.py           # pytest path setup (import statusfooter as a module)
│   ├── test_render.py        # Pure-function tests for render() and helpers
│   ├── test_signature.py     # Deterministic V4 signature test
│   ├── test_cache.py         # Cache hit/miss/atomic-write tests
│   └── test_main.py          # main() integration test with mocked fetch
└── docs/
    ├── superpowers/specs/2026-06-14-statusfooter-design.md
    └── superpowers/plans/2026-06-14-statusfooter.md
```

The single script is internally organized as named functions, all in one file:
- `load_config(path)` — read & validate JSON config
- `sign_request(ak, sk, body, now)` — produce signed headers (pure)
- `fetch_quota_usage(ak, sk)` — POST to OpenAPI, return `Result` dict
- `read_cache(path)` / `write_cache_atomic(path, payload)` — cache I/O
- `cached_fetch(config, now)` — orchestration with stale-cache fallback
- `format_countdown(seconds)` — pure helper
- `progress_bar(percent)` — pure helper
- `colorize(text, percent)` — pure helper
- `render(quota_result, now, stale)` — pure top-level renderer
- `main()` — entry point, exit-code 0 guarantee

---

## Task 0: Project scaffolding

**Files:**
- Create: `/home/ubuntu/projects/statusfooter/.gitignore`
- Create: `/home/ubuntu/projects/statusfooter/README.md`
- Create: `/home/ubuntu/projects/statusfooter/tests/conftest.py`

- [ ] **Step 1: Initialize git repo**

Run from `/home/ubuntu/projects/statusfooter`:

```bash
cd /home/ubuntu/projects/statusfooter
git init
git config user.email "dev@local"
git config user.name "statusfooter dev"
```

Expected: empty repo on default branch.

- [ ] **Step 2: Write `.gitignore`**

```
__pycache__/
*.pyc
.pytest_cache/
.venv/
.DS_Store
```

- [ ] **Step 3: Write `README.md` (stub — full content updated in final task)**

```markdown
# statusfooter

Compact Claude Code status line showing Volcengine Ark Coding Plan 5h / weekly / monthly quota usage.

See `docs/superpowers/specs/2026-06-14-statusfooter-design.md` for design.
```

- [ ] **Step 4: Write `tests/conftest.py`**

This makes the `statusfooter` executable importable as a module in tests. The script has no `.py` extension, so we use `importlib`.

```python
import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "statusfooter"

spec = importlib.util.spec_from_loader(
    "statusfooter",
    importlib.machinery.SourceFileLoader("statusfooter", str(SCRIPT)),
)
module = importlib.util.module_from_spec(spec)
sys.modules["statusfooter"] = module
# Defer load until first import in a test (script may not exist yet for Task 0)
def _load():
    spec.loader.exec_module(module)
    return module
sys.modules["statusfooter"]._load = _load  # type: ignore[attr-defined]
```

- [ ] **Step 5: Verify pytest is available**

Run:

```bash
python3 -m pytest --version
```

Expected: pytest version printed. If not installed, run:

```bash
python3 -m pip install --user pytest
```

- [ ] **Step 6: Commit**

```bash
cd /home/ubuntu/projects/statusfooter
git add .gitignore README.md tests/conftest.py docs/
git commit -m "chore: initial scaffolding"
```

---

## Task 1: `progress_bar()` — pure helper

**Files:**
- Create: `/home/ubuntu/projects/statusfooter/statusfooter` (initial shebang + this function)
- Create: `/home/ubuntu/projects/statusfooter/tests/test_render.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_render.py`:

```python
import sys
from pathlib import Path

# Force-load the script as module
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import importlib.util
spec = importlib.util.spec_from_loader(
    "statusfooter",
    importlib.machinery.SourceFileLoader("statusfooter", str(ROOT / "statusfooter")),
)
sf = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sf)


def test_progress_bar_empty():
    assert sf.progress_bar(0) == "░░░"

def test_progress_bar_low():
    assert sf.progress_bar(10) == "░░░"

def test_progress_bar_one_third_boundary():
    assert sf.progress_bar(33) == "▓░░"

def test_progress_bar_two_thirds_boundary():
    assert sf.progress_bar(67) == "▓▓░"

def test_progress_bar_high():
    assert sf.progress_bar(80) == "▓▓░"

def test_progress_bar_full():
    assert sf.progress_bar(100) == "▓▓▓"

def test_progress_bar_overflow():
    assert sf.progress_bar(150) == "▓▓▓"

def test_progress_bar_just_below_full():
    assert sf.progress_bar(99) == "▓▓░"
```

- [ ] **Step 2: Run test, verify failure**

Run:

```bash
cd /home/ubuntu/projects/statusfooter
python3 -m pytest tests/test_render.py -v
```

Expected: collection error or `FileNotFoundError` for `statusfooter` script.

- [ ] **Step 3: Create the script with minimal `progress_bar`**

Create `statusfooter` (no `.py` extension):

```python
#!/usr/bin/env python3
"""statusfooter — Claude Code status line for Volcengine Ark Coding Plan."""

def progress_bar(percent: float) -> str:
    if percent < 33:
        return "░░░"
    if percent < 67:
        return "▓░░"
    if percent < 100:
        return "▓▓░"
    return "▓▓▓"
```

Make executable:

```bash
chmod +x /home/ubuntu/projects/statusfooter/statusfooter
```

- [ ] **Step 4: Run tests, verify pass**

Run:

```bash
python3 -m pytest tests/test_render.py -v
```

Expected: 8 passed.

- [ ] **Step 5: Commit**

```bash
git add statusfooter tests/test_render.py
git commit -m "feat: progress_bar helper with 3-cell rendering"
```

---

## Task 2: `format_countdown()` — pure helper

**Files:**
- Modify: `/home/ubuntu/projects/statusfooter/statusfooter`
- Modify: `/home/ubuntu/projects/statusfooter/tests/test_render.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_render.py`:

```python
def test_countdown_expired():
    assert sf.format_countdown(0) == "0m"
    assert sf.format_countdown(-30) == "0m"

def test_countdown_under_minute():
    assert sf.format_countdown(30) == "<1m"
    assert sf.format_countdown(59) == "<1m"

def test_countdown_minutes():
    assert sf.format_countdown(60) == "1m"
    assert sf.format_countdown(45 * 60) == "45m"
    assert sf.format_countdown(59 * 60 + 59) == "59m"

def test_countdown_hours():
    assert sf.format_countdown(60 * 60) == "1h0m"
    assert sf.format_countdown(60 * 60 + 19 * 60) == "1h19m"
    assert sf.format_countdown(23 * 3600 + 59 * 60) == "23h59m"

def test_countdown_days_under_week():
    assert sf.format_countdown(24 * 3600) == "1d0h"
    assert sf.format_countdown(2 * 24 * 3600 + 3 * 3600) == "2d3h"
    assert sf.format_countdown(6 * 24 * 3600 + 23 * 3600) == "6d23h"

def test_countdown_days_over_week():
    assert sf.format_countdown(7 * 24 * 3600) == "7d"
    assert sf.format_countdown(26 * 24 * 3600 + 5 * 3600) == "26d"
```

- [ ] **Step 2: Run test, verify failure**

Run:

```bash
python3 -m pytest tests/test_render.py -v
```

Expected: 6 new tests fail with `AttributeError: module 'statusfooter' has no attribute 'format_countdown'`.

- [ ] **Step 3: Implement `format_countdown`**

Append to `statusfooter` (after `progress_bar`):

```python
def format_countdown(seconds: int) -> str:
    if seconds <= 0:
        return "0m"
    if seconds < 60:
        return "<1m"
    if seconds < 3600:
        return f"{seconds // 60}m"
    if seconds < 86400:
        h = seconds // 3600
        m = (seconds % 3600) // 60
        return f"{h}h{m}m"
    if seconds < 7 * 86400:
        d = seconds // 86400
        h = (seconds % 86400) // 3600
        return f"{d}d{h}h"
    return f"{seconds // 86400}d"
```

- [ ] **Step 4: Run tests, verify pass**

Run:

```bash
python3 -m pytest tests/test_render.py -v
```

Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add statusfooter tests/test_render.py
git commit -m "feat: format_countdown helper"
```

---

## Task 3: `colorize()` — pure helper

**Files:**
- Modify: `/home/ubuntu/projects/statusfooter/statusfooter`
- Modify: `/home/ubuntu/projects/statusfooter/tests/test_render.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_render.py`:

```python
RESET = "\033[0m"

def test_colorize_below_60_no_color():
    assert sf.colorize("X", 0) == "X"
    assert sf.colorize("X", 59) == "X"

def test_colorize_60_to_80_yellow():
    assert sf.colorize("X", 60) == f"\033[33mX{RESET}"
    assert sf.colorize("X", 79) == f"\033[33mX{RESET}"

def test_colorize_80_plus_red():
    assert sf.colorize("X", 80) == f"\033[31mX{RESET}"
    assert sf.colorize("X", 100) == f"\033[31mX{RESET}"
    assert sf.colorize("X", 120) == f"\033[31mX{RESET}"
```

- [ ] **Step 2: Run test, verify failure**

Run:

```bash
python3 -m pytest tests/test_render.py -v
```

Expected: 3 new tests fail with `AttributeError`.

- [ ] **Step 3: Implement `colorize`**

Append to `statusfooter`:

```python
def colorize(text: str, percent: float) -> str:
    if percent >= 80:
        return f"\033[31m{text}\033[0m"
    if percent >= 60:
        return f"\033[33m{text}\033[0m"
    return text
```

- [ ] **Step 4: Run tests, verify pass**

Run:

```bash
python3 -m pytest tests/test_render.py -v
```

Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add statusfooter tests/test_render.py
git commit -m "feat: colorize helper with 60/80% thresholds"
```

---

## Task 4: `render()` — assemble final string

**Files:**
- Modify: `/home/ubuntu/projects/statusfooter/statusfooter`
- Modify: `/home/ubuntu/projects/statusfooter/tests/test_render.py`

This task wires the helpers into the full output. The renderer takes the API `Result` dict, current Unix time, and a `stale` flag.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_render.py`:

```python
SAMPLE_RESULT = {
    "Status": "Running",
    "UpdateTimestamp": 1781442276,
    "QuotaUsage": [
        {"Level": "weekly",  "Percent": 61.55, "ResetTimestamp": 1781452800},
        {"Level": "session", "Percent": 25.98, "ResetTimestamp": 1781447046},
        {"Level": "monthly", "Percent": 30.77, "ResetTimestamp": 1783699199},
    ],
}
NOW = 1781442276  # matches UpdateTimestamp; reset deltas:
# session: 1781447046 - 1781442276 = 4770s = 1h19m
# weekly:  1781452800 - 1781442276 = 10524s = 2h55m
# monthly: 1783699199 - 1781442276 = 2256923s = 26d

def test_render_normal():
    out = sf.render(SAMPLE_RESULT, NOW, stale=False)
    # Order is always 5h, W, M regardless of API order
    assert "5h 26% ▓░░" in out
    assert "W 62%" in out  # 61.55 rounds to 62
    assert "M 31% ▓░░" in out
    # countdown segment present in 5h/W/M order
    assert "↻5h 1h19m" in out
    assert "W 2h55m" in out
    assert "M 26d" in out
    # No stale marker
    assert "⚠" not in out

def test_render_stale_marker():
    out = sf.render(SAMPLE_RESULT, NOW, stale=True)
    assert out.endswith("⚠")

def test_render_color_thresholds():
    result = {
        "Status": "Running",
        "QuotaUsage": [
            {"Level": "session", "Percent": 50, "ResetTimestamp": NOW + 3600},
            {"Level": "weekly",  "Percent": 70, "ResetTimestamp": NOW + 3600},
            {"Level": "monthly", "Percent": 85, "ResetTimestamp": NOW + 3600},
        ],
    }
    out = sf.render(result, NOW, stale=False)
    # session 50% → no color
    assert "5h 50% ▓░░" in out
    # weekly 70% → yellow
    assert "\033[33mW 70% ▓▓░\033[0m" in out
    # monthly 85% → red
    assert "\033[31mM 85% ▓▓░\033[0m" in out

def test_render_unknown_status():
    result = {"Status": "Suspended", "QuotaUsage": []}
    out = sf.render(result, NOW, stale=False)
    assert out == "statusfooter: status=Suspended"

def test_render_skips_unknown_levels():
    result = {
        "Status": "Running",
        "QuotaUsage": [
            {"Level": "weekly", "Percent": 50, "ResetTimestamp": NOW + 3600},
            {"Level": "alien",  "Percent": 99, "ResetTimestamp": NOW + 3600},
        ],
    }
    out = sf.render(result, NOW, stale=False)
    assert "alien" not in out
    assert "W 50%" in out
```

- [ ] **Step 2: Run tests, verify failure**

Run:

```bash
python3 -m pytest tests/test_render.py -v
```

Expected: 5 new tests fail.

- [ ] **Step 3: Implement `render`**

Append to `statusfooter`:

```python
LEVEL_TO_LABEL = {"session": "5h", "weekly": "W", "monthly": "M"}
LABEL_ORDER = ["5h", "W", "M"]


def render(result: dict, now: int, stale: bool) -> str:
    status = result.get("Status", "")
    if status != "Running":
        return f"statusfooter: status={status}"

    by_label = {}
    for entry in result.get("QuotaUsage", []):
        label = LEVEL_TO_LABEL.get(entry.get("Level"))
        if label is None:
            continue
        by_label[label] = entry

    parts = []
    countdowns = []
    for label in LABEL_ORDER:
        entry = by_label.get(label)
        if entry is None:
            continue
        pct = round(entry.get("Percent", 0))
        bar = progress_bar(entry.get("Percent", 0))
        segment = f"{label} {pct}% {bar}"
        parts.append(colorize(segment, entry.get("Percent", 0)))

        reset_ts = entry.get("ResetTimestamp", now)
        countdowns.append(f"{label} {format_countdown(reset_ts - now)}")

    if not parts:
        return "statusfooter: bad resp"

    line = "  ".join(parts)
    if countdowns:
        # First countdown gets the ↻ prefix; rest joined with spaces
        first = "↻" + countdowns[0]
        rest = "  ".join(countdowns[1:])
        countdown_str = first + ("  " + rest if rest else "")
        line = f"{line}  {countdown_str}"

    if stale:
        line = f"{line} ⚠"
    return line
```

- [ ] **Step 4: Run tests, verify pass**

Run:

```bash
python3 -m pytest tests/test_render.py -v
```

Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add statusfooter tests/test_render.py
git commit -m "feat: render() — assemble full status line"
```

---

## Task 5: `sign_request()` — Volcengine V4 signing

**Files:**
- Modify: `/home/ubuntu/projects/statusfooter/statusfooter`
- Create: `/home/ubuntu/projects/statusfooter/tests/test_signature.py`

The signature algorithm was empirically validated against `open.volcengineapi.com` during brainstorming. We test it deterministically by pinning the timestamp.

- [ ] **Step 1: Write the failing test**

Create `tests/test_signature.py`:

```python
import sys
from pathlib import Path
import importlib.util

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
    # Signature is deterministic given fixed inputs
    assert "Signature=" in auth
    sig = auth.split("Signature=")[1]
    assert len(sig) == 64  # hex sha256
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
```

- [ ] **Step 2: Run test, verify failure**

Run:

```bash
python3 -m pytest tests/test_signature.py -v
```

Expected: tests fail with `AttributeError: module 'statusfooter' has no attribute 'sign_request'`.

- [ ] **Step 3: Implement `sign_request`**

Append to `statusfooter`:

```python
import hashlib
import hmac
import datetime as _dt


def _hmac_sha256(key: bytes, data: str) -> bytes:
    return hmac.new(key, data.encode("utf-8"), hashlib.sha256).digest()


def _hex_sha256(data: str) -> str:
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def sign_request(ak: str, sk: str, body: str, now: _dt.datetime,
                 action: str, version: str, host: str,
                 region: str, service: str) -> dict:
    x_date = now.strftime("%Y%m%dT%H%M%SZ")
    short_date = now.strftime("%Y%m%d")
    body_hash = _hex_sha256(body)

    canonical_query = f"Action={action}&Version={version}"
    signed_headers = "content-type;host;x-content-sha256;x-date"
    canonical_headers = (
        f"content-type:application/json\n"
        f"host:{host}\n"
        f"x-content-sha256:{body_hash}\n"
        f"x-date:{x_date}\n"
    )
    canonical_request = "\n".join([
        "POST", "/", canonical_query, canonical_headers, signed_headers, body_hash
    ])
    credential_scope = f"{short_date}/{region}/{service}/request"
    string_to_sign = "\n".join([
        "HMAC-SHA256", x_date, credential_scope, _hex_sha256(canonical_request)
    ])

    k_date = _hmac_sha256(sk.encode("utf-8"), short_date)
    k_region = _hmac_sha256(k_date, region)
    k_service = _hmac_sha256(k_region, service)
    k_signing = _hmac_sha256(k_service, "request")
    signature = hmac.new(k_signing, string_to_sign.encode("utf-8"),
                         hashlib.sha256).hexdigest()

    return {
        "Content-Type": "application/json",
        "Host": host,
        "X-Date": x_date,
        "X-Content-Sha256": body_hash,
        "Authorization": (
            f"HMAC-SHA256 Credential={ak}/{credential_scope}, "
            f"SignedHeaders={signed_headers}, Signature={signature}"
        ),
    }
```

- [ ] **Step 4: Run tests, verify pass**

Run:

```bash
python3 -m pytest tests/test_signature.py -v
```

Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add statusfooter tests/test_signature.py
git commit -m "feat: Volcengine V4 request signing"
```

---

## Task 6: `fetch_quota_usage()` — POST to OpenAPI

**Files:**
- Modify: `/home/ubuntu/projects/statusfooter/statusfooter`
- Modify: `/home/ubuntu/projects/statusfooter/tests/test_signature.py` (or new test file)

This task wraps `sign_request` with `urllib.request` and parses the response. We test it by monkeypatching `urllib.request.urlopen`.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_signature.py`:

```python
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
    # Body must be {} (empty JSON object)
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
```

- [ ] **Step 2: Run test, verify failure**

Run:

```bash
python3 -m pytest tests/test_signature.py -v
```

Expected: 2 new tests fail with `AttributeError` for `fetch_quota_usage` / `FetchError` / `urllib`.

- [ ] **Step 3: Implement `fetch_quota_usage` and `FetchError`**

Append to `statusfooter`:

```python
import urllib.request
import urllib.error
import json as _json


HOST = "open.volcengineapi.com"
ACTION = "GetCodingPlanUsage"
VERSION = "2024-01-01"
REGION = "cn-beijing"
SERVICE = "ark"


class FetchError(Exception):
    pass


def fetch_quota_usage(ak: str, sk: str) -> dict:
    body = "{}"
    headers = sign_request(
        ak=ak, sk=sk, body=body, now=_dt.datetime.utcnow(),
        action=ACTION, version=VERSION, host=HOST,
        region=REGION, service=SERVICE,
    )
    url = f"https://{HOST}/?Action={ACTION}&Version={VERSION}"
    req = urllib.request.Request(url, data=body.encode("utf-8"),
                                 headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            payload = _json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, urllib.error.HTTPError, OSError, ValueError) as e:
        raise FetchError(str(e)) from e

    if "Result" not in payload:
        raise FetchError(f"unexpected response: {payload}")
    return payload["Result"]
```

- [ ] **Step 4: Run tests, verify pass**

Run:

```bash
python3 -m pytest tests/test_signature.py -v
```

Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add statusfooter tests/test_signature.py
git commit -m "feat: fetch_quota_usage HTTP client"
```

---

## Task 7: Cache layer — `read_cache`, `write_cache_atomic`, `cached_fetch`

**Files:**
- Modify: `/home/ubuntu/projects/statusfooter/statusfooter`
- Create: `/home/ubuntu/projects/statusfooter/tests/test_cache.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_cache.py`:

```python
import sys, os, time, json
from pathlib import Path
import importlib.util
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
    # Simulate write failure mid-flight: should not corrupt prior file
    def fail_replace(*a, **kw):
        raise OSError("disk full")
    monkeypatch.setattr(sf.os, "replace", fail_replace)
    with pytest.raises(OSError):
        sf.write_cache_atomic(p, {"Status": "Other"})
    # Original content survives
    assert sf.read_cache(p) == SAMPLE_RESULT


def test_cached_fetch_hit(tmp_path, monkeypatch):
    cache_path = tmp_path / "cache.json"
    sf.write_cache_atomic(cache_path, SAMPLE_RESULT)

    def should_not_call(*a, **k):
        raise AssertionError("fetch should not be called on cache hit")

    monkeypatch.setattr(sf, "fetch_quota_usage", should_not_call)
    config = {"ak": "AK", "sk": "SK", "cache_ttl": 60}
    result, stale = sf.cached_fetch(config, cache_path, now=time.time())
    assert result == SAMPLE_RESULT
    assert stale is False


def test_cached_fetch_miss_calls_api(tmp_path, monkeypatch):
    cache_path = tmp_path / "cache.json"
    NEW_RESULT = {"Status": "Running", "QuotaUsage": []}

    def fake_fetch(ak, sk):
        return NEW_RESULT

    monkeypatch.setattr(sf, "fetch_quota_usage", fake_fetch)
    config = {"ak": "AK", "sk": "SK", "cache_ttl": 60}
    result, stale = sf.cached_fetch(config, cache_path, now=time.time())
    assert result == NEW_RESULT
    assert stale is False
    # Cache was written
    assert sf.read_cache(cache_path) == NEW_RESULT


def test_cached_fetch_expired(tmp_path, monkeypatch):
    cache_path = tmp_path / "cache.json"
    sf.write_cache_atomic(cache_path, SAMPLE_RESULT)
    # Make file old
    old = time.time() - 3600
    os.utime(cache_path, (old, old))

    NEW_RESULT = {"Status": "Running", "QuotaUsage": []}
    monkeypatch.setattr(sf, "fetch_quota_usage", lambda ak, sk: NEW_RESULT)

    config = {"ak": "AK", "sk": "SK", "cache_ttl": 60}
    result, stale = sf.cached_fetch(config, cache_path, now=time.time())
    assert result == NEW_RESULT
    assert stale is False


def test_cached_fetch_api_fails_uses_stale(tmp_path, monkeypatch):
    cache_path = tmp_path / "cache.json"
    sf.write_cache_atomic(cache_path, SAMPLE_RESULT)
    old = time.time() - 3600
    os.utime(cache_path, (old, old))

    def fail(ak, sk):
        raise sf.FetchError("network down")

    monkeypatch.setattr(sf, "fetch_quota_usage", fail)
    config = {"ak": "AK", "sk": "SK", "cache_ttl": 60}
    result, stale = sf.cached_fetch(config, cache_path, now=time.time())
    assert result == SAMPLE_RESULT
    assert stale is True


def test_cached_fetch_api_fails_no_cache(tmp_path, monkeypatch):
    cache_path = tmp_path / "no_cache.json"

    def fail(ak, sk):
        raise sf.FetchError("network down")

    monkeypatch.setattr(sf, "fetch_quota_usage", fail)
    config = {"ak": "AK", "sk": "SK", "cache_ttl": 60}
    with pytest.raises(sf.FetchError):
        sf.cached_fetch(config, cache_path, now=time.time())
```

- [ ] **Step 2: Run test, verify failure**

Run:

```bash
python3 -m pytest tests/test_cache.py -v
```

Expected: collection succeeds but tests fail (`AttributeError` for missing functions).

- [ ] **Step 3: Implement cache functions**

Append to `statusfooter`:

```python
import os
import tempfile


def read_cache(path) -> dict | None:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return _json.load(f)
    except (FileNotFoundError, _json.JSONDecodeError):
        return None


def write_cache_atomic(path, payload: dict) -> None:
    path = str(path)
    dir_ = os.path.dirname(path) or "."
    os.makedirs(dir_, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=dir_, prefix=".cache.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            _json.dump(payload, f)
        os.replace(tmp, path)
    except Exception:
        try:
            os.unlink(tmp)
        except FileNotFoundError:
            pass
        raise


def cached_fetch(config: dict, cache_path, now: float) -> tuple[dict, bool]:
    """Return (result_dict, is_stale).

    Cache hit (mtime within ttl) → cached result, stale=False.
    Cache miss → fetch, write cache, stale=False.
    Fetch fails with stale cache present → return stale cache, stale=True.
    Fetch fails with no cache → raise FetchError.
    """
    ttl = config.get("cache_ttl", 60)
    cache_path = str(cache_path)
    cached = read_cache(cache_path)
    fresh = False
    if cached is not None and os.path.exists(cache_path):
        mtime = os.path.getmtime(cache_path)
        if now - mtime < ttl:
            fresh = True

    if fresh:
        return cached, False

    try:
        result = fetch_quota_usage(config["ak"], config["sk"])
        write_cache_atomic(cache_path, result)
        return result, False
    except FetchError:
        if cached is not None:
            return cached, True
        raise
```

- [ ] **Step 4: Run tests, verify pass**

Run:

```bash
python3 -m pytest tests/test_cache.py -v
```

Expected: 9 passed.

- [ ] **Step 5: Commit**

```bash
git add statusfooter tests/test_cache.py
git commit -m "feat: cache layer with stale-fallback"
```

---

## Task 8: `load_config()` — read JSON config

**Files:**
- Modify: `/home/ubuntu/projects/statusfooter/statusfooter`
- Modify: `/home/ubuntu/projects/statusfooter/tests/test_cache.py` (or new test file)

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_cache.py`:

```python
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
```

- [ ] **Step 2: Run test, verify failure**

Run:

```bash
python3 -m pytest tests/test_cache.py -v
```

Expected: 5 new tests fail.

- [ ] **Step 3: Implement `load_config` and `ConfigError`**

Append to `statusfooter`:

```python
class ConfigError(Exception):
    pass


def load_config(path) -> dict:
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = _json.load(f)
    except (FileNotFoundError, _json.JSONDecodeError) as e:
        raise ConfigError(str(e)) from e
    for key in ("ak", "sk"):
        if not data.get(key):
            raise ConfigError(f"missing required key: {key}")
    data.setdefault("cache_ttl", 60)
    return data
```

- [ ] **Step 4: Run tests, verify pass**

Run:

```bash
python3 -m pytest tests/test_cache.py -v
```

Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add statusfooter tests/test_cache.py
git commit -m "feat: load_config with validation"
```

---

## Task 9: `main()` — entry point with exit-0 guarantee

**Files:**
- Modify: `/home/ubuntu/projects/statusfooter/statusfooter`
- Create: `/home/ubuntu/projects/statusfooter/tests/test_main.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_main.py`:

```python
import sys, os, json, time
from pathlib import Path
import importlib.util
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
    monkeypatch.setattr(sf, "fetch_quota_usage", lambda ak, sk: fake_result)

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

    def fail(ak, sk):
        raise sf.FetchError("boom")

    monkeypatch.setattr(sf, "fetch_quota_usage", fail)

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
```

- [ ] **Step 2: Run test, verify failure**

Run:

```bash
python3 -m pytest tests/test_main.py -v
```

Expected: tests fail (no `main`, no `CONFIG_PATH`, etc.).

- [ ] **Step 3: Implement `main`**

Append to `statusfooter`:

```python
import time as _time


CONFIG_PATH = os.path.expanduser("~/.config/statusfooter/config.json")
CACHE_PATH = os.path.expanduser("~/.cache/statusfooter/usage.json")


def main() -> int:
    try:
        try:
            config = load_config(CONFIG_PATH)
        except ConfigError:
            print("statusfooter: missing config")
            return 0

        try:
            result, stale = cached_fetch(config, CACHE_PATH, now=_time.time())
        except FetchError:
            print("statusfooter: net err")
            return 0

        try:
            line = render(result, now=int(_time.time()), stale=stale)
        except Exception:
            print("statusfooter: bad resp")
            return 0

        print(line)
        return 0
    except Exception:
        print("statusfooter: err")
        return 0


if __name__ == "__main__":
    sys.exit(main())
```

Also add `import sys` near the top (just below the docstring) if it isn't there already — search the file for `import sys` first.

- [ ] **Step 4: Run all tests, verify pass**

Run:

```bash
python3 -m pytest -v
```

Expected: all tests pass across `test_render.py`, `test_signature.py`, `test_cache.py`, `test_main.py`.

- [ ] **Step 5: Manually run the script with no config**

Run:

```bash
HOME=/tmp/sf_empty mkdir -p /tmp/sf_empty
HOME=/tmp/sf_empty /home/ubuntu/projects/statusfooter/statusfooter
echo "exit code: $?"
```

Expected output:

```
statusfooter: missing config
exit code: 0
```

- [ ] **Step 6: Commit**

```bash
git add statusfooter tests/test_main.py
git commit -m "feat: main() entrypoint with exit-0 guarantee"
```

---

## Task 10: `install.sh` — installer

**Files:**
- Create: `/home/ubuntu/projects/statusfooter/install.sh`

- [ ] **Step 1: Write `install.sh`**

```bash
#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEST="${HOME}/.local/bin/statusfooter"
CONFIG_DIR="${HOME}/.config/statusfooter"
CACHE_DIR="${HOME}/.cache/statusfooter"
CONFIG_FILE="${CONFIG_DIR}/config.json"

mkdir -p "$(dirname "$DEST")" "$CONFIG_DIR" "$CACHE_DIR"

install -m755 "${SCRIPT_DIR}/statusfooter" "$DEST"
echo "Installed: $DEST"

if [ ! -f "$CONFIG_FILE" ]; then
  cat > "$CONFIG_FILE" <<EOF
{
  "ak": "REPLACE_ME",
  "sk": "REPLACE_ME",
  "cache_ttl": 60
}
EOF
  chmod 600 "$CONFIG_FILE"
  echo "Created: $CONFIG_FILE  (chmod 600)"
  echo "→ Edit it and replace REPLACE_ME with your Volcengine AccessKeyId / SecretAccessKey."
else
  echo "Existing config left untouched: $CONFIG_FILE"
fi

cat <<EOF

Next: add this to ~/.claude/settings.json under the top-level object:

  "statusLine": {
    "type": "command",
    "command": "${DEST}"
  }

(If \$HOME/.local/bin is on PATH, the command can just be "statusfooter".)
EOF
```

- [ ] **Step 2: Make executable and run dry-run smoke test**

```bash
chmod +x /home/ubuntu/projects/statusfooter/install.sh
HOME=/tmp/sf_install_test mkdir -p /tmp/sf_install_test
HOME=/tmp/sf_install_test /home/ubuntu/projects/statusfooter/install.sh
test -x /tmp/sf_install_test/.local/bin/statusfooter && echo "installed OK"
test -f /tmp/sf_install_test/.config/statusfooter/config.json && echo "config OK"
stat -c '%a' /tmp/sf_install_test/.config/statusfooter/config.json
```

Expected: `installed OK`, `config OK`, mode `600`.

- [ ] **Step 3: Commit**

```bash
git add install.sh
git commit -m "chore: idempotent installer"
```

---

## Task 11: README.md — final user-facing documentation

**Files:**
- Modify: `/home/ubuntu/projects/statusfooter/README.md`

- [ ] **Step 1: Replace README content**

Overwrite `README.md` with:

````markdown
# statusfooter

Compact Claude Code status line showing your Volcengine Ark **Coding Plan** quota usage:

```
5h 26% ▓░░  W 62% ▓▓▓  M 31% ▓░░  ↻5h 1h19m  W 2h55m  M 26d
```

- Three rolling windows: **5h** (session), **W** (weekly), **M** (monthly)
- Color-coded: yellow ≥60%, red ≥80%
- Reset countdowns for each window
- 60-second local cache so the status line is fast and doesn't hammer the API
- Pure Python 3 stdlib, single file, zero deps

## Install

```bash
git clone <this-repo> statusfooter
cd statusfooter
./install.sh
```

Then edit `~/.config/statusfooter/config.json` and fill in your Volcengine
**AccessKeyId** and **SecretAccessKey**:

```json
{
  "ak": "AKLT...",
  "sk": "...",
  "cache_ttl": 60
}
```

> Get keys at: Volcengine Console → top-right avatar → **API Access Keys**.
> Recommend creating a sub-account with read-only `ark` permissions.

## Wire into Claude Code

Add to `~/.claude/settings.json`:

```json
{
  "statusLine": {
    "type": "command",
    "command": "/home/YOU/.local/bin/statusfooter"
  }
}
```

## Manually verify

```bash
~/.local/bin/statusfooter
```

You should see the formatted line. If you see `statusfooter: missing config`, edit the config file. If you see `statusfooter: net err`, check connectivity to `open.volcengineapi.com`.

## Run tests

```bash
python3 -m pytest -v
```

## Architecture

See `docs/superpowers/specs/2026-06-14-statusfooter-design.md`.
````

- [ ] **Step 2: Commit**

```bash
git add README.md
git commit -m "docs: full README"
```

---

## Task 12: End-to-end verification

**Files:** none (verification only)

- [ ] **Step 1: Run the full test suite**

```bash
cd /home/ubuntu/projects/statusfooter
python3 -m pytest -v
```

Expected: all tests pass (counts approximately: 8 progress_bar + 6 countdown + 3 colorize + 5 render + 4 signature/fetch + 9 cache + 5 config + 4 main = ~44 tests).

- [ ] **Step 2: Smoke test with real credentials**

Make sure `~/.config/statusfooter/config.json` has the real AK/SK:

```json
{
  "ak": "AKLT_REPLACE_ME",
  "sk": "TVdK_REPLACE_ME",
  "cache_ttl": 60
}
```

Then run:

```bash
chmod 600 ~/.config/statusfooter/config.json
~/.local/bin/statusfooter
```

Expected: a single line like `5h NN% ▓░░  W NN% ▓░░  M NN% ▓░░  ↻5h ...  W ...  M ...`

- [ ] **Step 3: Time it (cache cold and warm)**

```bash
rm -f ~/.cache/statusfooter/usage.json
time ~/.local/bin/statusfooter   # cold: should be < 800ms
time ~/.local/bin/statusfooter   # warm: should be < 30ms
```

Expected: warm run is dramatically faster (cache hit, no network).

- [ ] **Step 4: Failure-mode smoke tests**

Bad config → graceful:

```bash
mv ~/.config/statusfooter/config.json /tmp/cfg.bak
~/.local/bin/statusfooter
echo "exit: $?"
mv /tmp/cfg.bak ~/.config/statusfooter/config.json
```

Expected: prints `statusfooter: missing config`, exit 0.

Network blocked → stale cache used:

```bash
~/.local/bin/statusfooter   # populate cache
# Force expire cache + simulate offline by pointing host nowhere
touch -d "2 hours ago" ~/.cache/statusfooter/usage.json
sudo bash -c 'echo "127.0.0.2 open.volcengineapi.com" >> /etc/hosts'
~/.local/bin/statusfooter   # should show ⚠ marker on stale data
sudo sed -i '/open.volcengineapi.com/d' /etc/hosts
```

Expected: line ends with ` ⚠`, exit 0.

> Note: If you don't have sudo to edit /etc/hosts, skip this case — the cache test in `test_cache.py` already exercises the same code path.

- [ ] **Step 5: Wire into Claude Code and visually confirm**

Add to `~/.claude/settings.json`:

```json
"statusLine": {
  "type": "command",
  "command": "/root/.local/bin/statusfooter"
}
```

(Adjust path if your `$HOME` is different.)

Start a new Claude Code session. Visually confirm the bottom of the terminal shows the formatted status line.

- [ ] **Step 6: Final commit if anything changed**

```bash
cd /home/ubuntu/projects/statusfooter
git status
# If anything was modified during smoke testing:
git add -A && git commit -m "chore: end-to-end verification adjustments" || echo "nothing to commit"
```

---

## Self-Review

**Spec coverage check:**

| Spec section | Implemented in |
|---|---|
| Data source: `GetCodingPlanUsage` POST | Task 6 |
| V4 signing | Task 5 |
| `Result` field semantics (Level/Percent/ResetTimestamp) | Task 4 (render) + Task 6 (parse) |
| Single-script Python stdlib only | All tasks |
| `load_config` reads `~/.config/statusfooter/config.json` | Task 8 |
| `fetch_quota_usage` calls API | Task 6 |
| `cached_fetch` 60s TTL + stale fallback | Task 7 |
| `render` outputs ANSI-colored line | Task 4 |
| `main` orchestrates with exit-0 guarantee | Task 9 |
| Config file (JSON) with `ak`, `sk`, `cache_ttl` | Task 8 + 10 |
| Cache file under `~/.cache/statusfooter/usage.json` | Task 7 + 9 |
| Atomic writes (temp + rename) | Task 7 |
| Render rules: 3-cell bar at 33/67/100 boundaries | Task 1 |
| Color thresholds 60/80% | Task 3 |
| Countdown format (`<1m` / `45m` / `1h19m` / `2d3h` / `26d` / `0m`) | Task 2 |
| Output order `5h → W → M` | Task 4 |
| Status != Running → `statusfooter: status=X` | Task 4 |
| Stale cache → trailing `⚠` | Task 4 |
| Errors all → exit 0 | Task 9 |
| Installer | Task 10 |
| Tests for render, signature, cache, main | Tasks 1–9 |
| Manual verification checklist | Task 12 |

No gaps.

**Placeholder scan:** No TBDs, no "implement later", no "similar to Task N", no missing code blocks.

**Type / name consistency:**
- `progress_bar(percent)` — same signature in Tasks 1, 4
- `format_countdown(seconds)` — same in Tasks 2, 4
- `colorize(text, percent)` — same in Tasks 3, 4
- `sign_request(ak, sk, body, now, action, version, host, region, service)` — same in Tasks 5, 6
- `fetch_quota_usage(ak, sk)` — same in Tasks 6, 7, 9
- `read_cache(path)`, `write_cache_atomic(path, payload)`, `cached_fetch(config, cache_path, now)` — same in Tasks 7, 9
- `load_config(path)` returns dict with `ak`, `sk`, `cache_ttl` — same in Tasks 8, 9
- `render(result, now, stale)` — same in Tasks 4, 9
- `main()` returns int — Task 9
- `FetchError`, `ConfigError` — defined in Tasks 6 / 8, used in 7 / 9

All consistent.
