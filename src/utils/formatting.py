"""Display helpers shared by pages and reports."""
from __future__ import annotations
from config.settings import CURRENCY_SYMBOL


def kes(value, millions: bool = False) -> str:
    """Full, non-abbreviated KES figure by default (e.g. KES 7,704,313)."""
    if value is None or value != value:
        return "N/A"
    if millions:
        return f"{CURRENCY_SYMBOL} {value / 1_000_000:,.2f}M"
    return f"{CURRENCY_SYMBOL} {value:,.0f}"


def pct(value, decimals: int = 1) -> str:
    return "N/A" if value is None or value != value else f"{value:.{decimals}f}%"


# Status styling. Amber is a bright orange-yellow with DARK text so it cannot be mistaken for the crimson red; each status also has a
# distinct shape marker, so the meaning never depends on colour alone.
RAG_STYLE = {
    "GREEN": {"bg": "#1a7f37", "fg": "#ffffff", "marker": "\u25CF"},       # filled circle
    "AMBER": {"bg": "#f5a300", "fg": "#1f1f1f", "marker": "\u25B2"},       # triangle
    "RED": {"bg": "#c92a2a", "fg": "#ffffff", "marker": "\u25A0"},         # square
    "NOT RATED": {"bg": "#6b7280", "fg": "#ffffff", "marker": "\u25C6"},   # diamond
}
GAUGE_STEPS = {"RED": "#f4a6a6", "AMBER": "#ffd666", "GREEN": "#b7e1b7"}


def rag_color(status: str) -> str:
    return RAG_STYLE.get(status, RAG_STYLE["NOT RATED"])["bg"]


def rag_text_color(status: str) -> str:
    return RAG_STYLE.get(status, RAG_STYLE["NOT RATED"])["fg"]


def rag_label(status: str, text: str | None = None) -> str:
    """Marker + status text, e.g. '\u25B2 AMBER'."""
    return f"{RAG_STYLE.get(status, RAG_STYLE['NOT RATED'])['marker']} {text or status}"


def rag_badge_md(status: str, label: str | None = None) -> str:
    st = RAG_STYLE.get(status, RAG_STYLE["NOT RATED"])
    return (f'<span style="background-color:{st["bg"]};color:{st["fg"]};padding:2px 10px;'
            f'border-radius:10px;font-weight:700;font-size:0.9em;">{rag_label(status, label)}</span>')


def dq_bands_caption(dq=None) -> str:
    """Explains the Data Reliability bands (stricter than the Financial Health bands) and, when relevant, the inventory cap."""
    from config.settings import DQ_STATUS_BANDS
    g, a = DQ_STATUS_BANDS["GREEN"], DQ_STATUS_BANDS["AMBER"]
    text = (f"Data Reliability bands (different from the Financial Health bands): \u25CF {g}+ GREEN, \u25B2 {a}\u2013{g - 1} AMBER, "
            f"\u25A0 below {a} RED.")
    if dq is not None and getattr(dq, "inventory_assessed", True) and not dq.inventory_integrity_ok:
        text += (f" The score is capped at {a - 1} (RED) because inventory records are inconsistent (negative reconstructed stock), "
                 "whatever the other data checks score.")
    return text


def signed_kes(value) -> str:
    """Signed amount that STARTS with the sign (e.g. '-KES 70,153' / '+KES 70,153'). Streamlit's st.metric reads the first
    character of a delta string to choose the arrow and colour, so '+'/'-' must come first, not after the currency."""
    if value is None or value != value:
        return "N/A"
    sign = "-" if value < 0 else "+"
    return f"{sign}{CURRENCY_SYMBOL} {abs(value):,.0f}"


# One colour per measure, reused on every time-series chart
SERIES_COLORS = {"Revenue": "#1f77b4", "Gross profit": "#2ca02c", "Operating profit": "#d62728", "Operating expenses": "#ff7f0e"}
