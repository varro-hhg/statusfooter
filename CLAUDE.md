# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
python3 -m pytest -v              # run full test suite (66 tests, < 0.1s)
python3 -m pytest tests/test_render.py -v   # run a single test file
python3 -m pytest tests/test_render.py::test_render_normal -v  # run a single test
./install.sh                       # install to ~/.local/bin/statusfooter
```

## Architecture

**Single-file script** (`statusfooter`) — a Claude Code `statusLine` command that polls Volcengine Ark Coding Plan usage and renders a compact, color-coded status line. Zero dependencies (stdlib only). Python 3.8+ (`from __future__ import annotations` for `X | None` syntax).

### Data flow

```
Claude Code → main() → load_config() → cached_fetch()
                                    ├─ cache hit (mtime < TTL) → return cached
                                    └─ cache miss/expired → fetch_<provider>()
                                            ├─ HMAC-SHA256 sign_request() (volcengine)
                                            ├─ urllib GET/POST to provider API
                                            ├─ success → write_cache_atomic() → return result
                                            └─ FetchError → return stale cache (stale=True) or raise
                              → render(provider=...) → stdout line + exit 0
```

### Key constraints

- **Always exits 0**: every error path in `main()` prints a human-readable string and returns 0, so Claude Code status bar never blanks out.
- **Atomic cache writes**: `write_cache_atomic` uses `tempfile.mkstemp` + `os.replace` to avoid partial writes.
- **Stale cache fallback**: if the API is unreachable and a previous cache exists, the old data is rendered with a trailing `⚠`.
- **Optional stdin model prefix**: when Claude Code invokes the command, it pipes a JSON blob on stdin containing `model.display_name`. `read_stdin_model_name` extracts it; `render` prepends it to the output line. Non-interactive runs (or malformed stdin) silently skip it.

### Module layout (single file)

| Section | Purpose |
|---|---|
| `progress_bar`, `format_countdown`, `colorize` | Pure rendering helpers, easy to unit-test |
| `render()` | Builds the status line from the API result dict; owns label ordering (`5h`/`4h`, `W`, `M`) and countdown format |
| `sign_request()` | Volcengine HMAC-SHA256 V4 signing (date-keyed derivation chain) |
| `fetch_volcengine_ark()` | POST + parse `GetCodingPlanUsage` API response |
| `fetch_minimax()` | GET + parse MiniMax Coding Plan remains API (4h + weekly) |
| `read_cache`, `write_cache_atomic`, `cached_fetch` | File-based TTL cache layer |
| `load_config()` | Reads `~/.config/statusfooter/config.json`; supports old flat format (`ak`/`sk`) and new multi-provider format (`providers` dict + `active`) |
| `read_stdin_model_name()` | Parses stdin JSON for optional model display name |
| `main()` | Orchestrator — resolves provider by `_provider` key, chains config → stdin → cache → render, catches everything |

### Testing pattern

Tests import the script as a module via `importlib.util.SourceFileLoader` (each test file re-loads from disk). Network calls are patched with `monkeypatch`; time-sensitive cache tests pass a `now` parameter. Provider dispatch uses `globals().get(f"fetch_{provider_name}")`, so monkeypatching the fetch function on the module object works. `conftest.py` pre-loads the module but tests load independently.
