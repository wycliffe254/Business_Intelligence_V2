"""Static guards for the Streamlit pages."""
import ast, glob
from pathlib import Path
from tests.helpers import *

ROOT = Path(__file__).resolve().parents[1]


def test_no_standalone_non_call_expressions_in_pages():
    """Streamlit 'magic' auto-displays any standalone expression that is not a plain call. A one-line
    `st.x(...) if cond else st.y(...)` therefore prints the returned object's internals on the page (a past bug)."""
    for f in ["app.py"] + sorted(str(p.relative_to(ROOT)) for p in (ROOT / "pages").glob("*.py")):
        tree = ast.parse((ROOT / f).read_text())
        bad = [n.lineno for n in ast.walk(tree) if isinstance(n, ast.Expr) and not isinstance(n.value, (ast.Call, ast.Constant))]
        assert not bad, f"{f}: standalone expression(s) on line(s) {bad}; use an if/else statement"

def test_no_deprecated_use_container_width():
    for f in ["app.py"] + sorted(str(p.relative_to(ROOT)) for p in (ROOT / "pages").glob("*.py")):
        assert "use_container_width" not in (ROOT / f).read_text(), f


def test_signed_amount_starts_with_sign_so_streamlit_shows_the_right_arrow():
    from src.utils.formatting import signed_kes
    assert signed_kes(-70153).startswith("-") and signed_kes(70153).startswith("+") and signed_kes(float("nan")) == "N/A"

def test_metric_deltas_never_use_plain_kes_formatting():
    for f in ["app.py"] + sorted(str(p.relative_to(ROOT)) for p in (ROOT / "pages").glob("*.py")):
        assert "delta=kes(" not in (ROOT / f).read_text(), f"{f}: use signed_kes() so the arrow direction is correct"

def test_monthly_time_series_charts_are_line_charts():
    for f in ["app.py", "pages/2_Financial_Performance.py"]:
        src = (ROOT / f).read_text()
        assert "go.Bar(x=m[" not in src, f"{f}: monthly series should be lines, not bars"
