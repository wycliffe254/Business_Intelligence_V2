"""Run every test without pytest:  python tests/run_all.py   (pytest tests/ also works)."""
import importlib, sys, traceback
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
passed = failed = 0
for name in ["test_cleaning", "test_kpis", "test_scoring", "test_explainability", "test_flexible_schema", "test_pages_static", "test_column_matching"]:
    mod = importlib.import_module(f"tests.{name}")
    for fn in sorted(n for n in dir(mod) if n.startswith("test_")):
        try:
            getattr(mod, fn)(); passed += 1
        except Exception:
            failed += 1; print("FAIL", name, fn); traceback.print_exc()
print(f"PASSED {passed}, FAILED {failed}")
sys.exit(1 if failed else 0)
