import importlib.util
import importlib.machinery
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
