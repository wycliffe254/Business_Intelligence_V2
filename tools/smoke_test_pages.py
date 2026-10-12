"""
Executes app.py and every page script against several datasets using lightweight stand-ins for streamlit and plotly.
This does NOT test the visual layout; it catches runtime errors (KeyError, NaN formatting, empty-data crashes) in page code.

    python tools/smoke_test_pages.py
"""
import io, os, runpy, sys, traceback
from pathlib import Path
from types import ModuleType

ROOT = Path(__file__).resolve().parents[1]
os.chdir(ROOT)
sys.path.insert(0, str(ROOT))


class Stub:
    def __call__(self, *a, **k): return Stub()
    def __getattr__(self, n): return Stub()
    def __enter__(self): return Stub()
    def __exit__(self, *a): return False
    def __iter__(self): return iter([])
    def __bool__(self): return False


class StopPage(Exception):
    pass


class FakeUpload:
    def __init__(self, text, name="upload.csv"):
        self._b, self.name = text.encode(), name
    def getvalue(self): return self._b


class FakeSt(ModuleType):
    def __init__(self):
        super().__init__("streamlit")
        self.session_state, self.upload = {}, None
        self.sidebar = self
        self.components = ModuleType("streamlit.components"); self.components.v1 = Stub()
    def __enter__(self): return self
    def __exit__(self, *a): return False
    def columns(self, spec, **k): return [Stub() for _ in range(spec if isinstance(spec, int) else len(spec))]
    def tabs(self, labels): return [Stub() for _ in labels]
    def selectbox(self, label, options, **k): return list(options)[0]
    def multiselect(self, *a, **k): return []
    def date_input(self, label, value=None, **k): return value
    def file_uploader(self, *a, **k): return self.upload
    def stop(self): raise StopPage()
    def cache_data(self, *a, **k):
        return (lambda f: f) if not (a and callable(a[0])) else a[0]
    def download_button(self, *a, **k): return False
    def button(self, *a, **k): return False
    def __getattr__(self, n):
        if n.startswith("__"): raise AttributeError(n)
        return Stub()


def install():
    st = FakeSt()
    sys.modules["streamlit"] = st
    sys.modules["streamlit.components"] = st.components
    sys.modules["streamlit.components.v1"] = st.components.v1
    for m in ["plotly", "plotly.graph_objects", "plotly.express"]:
        sys.modules[m] = Stub() if m != "plotly" else ModuleType("plotly")
    sys.modules["plotly"].graph_objects = sys.modules["plotly.graph_objects"]
    sys.modules["plotly"].express = sys.modules["plotly.express"]
    return st


DATASETS = {
    "original sample": None,
    "synthetic sample": (ROOT / "data/sample/thika_road_hardware_agrovet_synthetic_dataset.csv").read_text(),
    "partial: date+item+sales": "Date,Item,Sales\n" + "\n".join(f"2025-{m:02d}-05,Cement,{1000 + m * 40}" for m in range(1, 9)) + "\n",
    "partial: sales+cogs+expenses": "date,type,net_sales_kes,cogs_kes,expense_amount_kes\n" + "\n".join(
        f"2025-{m:02d}-10,SALE,{1000 + m * 50},{700 + m * 20},0\n2025-{m:02d}-15,EXPENSE,0,0,{150 + m}" for m in range(1, 9)) + "\n",
    "combined Amount + Type": "Date,Description,Amount (KES),Type\n" + "\n".join(
        f"2025-{m:02d}-05,Cement,{2000 + m * 50},Income\n2025-{m:02d}-20,Rent,{900 + m},Expense" for m in range(1, 9)) + "\n",
    "partial: expenses only": "date,expense_amount_kes\n2025-01-05,100\n2025-02-05,200\n",
}


def run_all():
    failures = 0
    for label, csv in DATASETS.items():
        st = install()
        for mod in [m for m in list(sys.modules) if m.startswith("src.") or m == "src"]:
            if mod != "src.ui_state":
                pass
        sys.modules.pop("src.ui_state", None)
        if csv is not None:
            st.upload = FakeUpload(csv)
        scripts = ["app.py"] + sorted(str(p.relative_to(ROOT)) for p in (ROOT / "pages").glob("*.py"))
        for script in scripts:
            try:
                runpy.run_path(str(ROOT / script), run_name="__main__")
                status = "ok"
            except StopPage:
                status = "ok (st.stop)"
            except Exception:
                status = "ERROR"
                failures += 1
                print(f"[{label}] {script}: ERROR"); traceback.print_exc()
            if status == "ERROR":
                continue
        print(f"[{label}] finished")
    print("SMOKE TEST:", "FAILED" if failures else "all pages ran without runtime errors")
    return failures


if __name__ == "__main__":
    sys.exit(1 if run_all() else 0)
