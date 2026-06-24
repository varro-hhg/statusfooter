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
    assert "5h 26% ░░░" in out
    assert "W 62%" in out  # 61.55 rounds to 62
    assert "M 31% ░░░" in out
    # countdown segment present in 5h/W/M order
    assert "↻5h 1h19m" in out
    assert "W 2h55m" in out
    assert "M 26d" in out
    # No stale marker
    assert "⚠" not in out

def test_render_stale_marker():
    out = sf.render(SAMPLE_RESULT, NOW, stale=True)
    assert out.endswith("⚠")

def test_render_with_model_prefix():
    out = sf.render(SAMPLE_RESULT, NOW, stale=False, model_name="Sonnet 4.5")
    assert out.startswith("Sonnet 4.5  ")
    # rest of the line is unchanged
    assert "5h 26% ░░░" in out
    assert "↻5h 1h19m" in out

def test_render_model_prefix_none_unchanged():
    base = sf.render(SAMPLE_RESULT, NOW, stale=False)
    with_none = sf.render(SAMPLE_RESULT, NOW, stale=False, model_name=None)
    assert base == with_none

def test_render_model_prefix_with_stale():
    out = sf.render(SAMPLE_RESULT, NOW, stale=True, model_name="GLM-5.1")
    assert out.startswith("GLM-5.1  ")
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


def test_render_all_unknown_levels_returns_bad_resp():
    result = {
        "Status": "Running",
        "QuotaUsage": [{"Level": "alien", "Percent": 99, "ResetTimestamp": NOW}],
    }
    assert sf.render(result, NOW, stale=False) == "statusfooter: bad resp"
