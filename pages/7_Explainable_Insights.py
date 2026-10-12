import streamlit as st
from src.ui_state import get_result

st.set_page_config(page_title="Explainable Insights", layout="wide")
st.title("Explainable Insights")
r = get_result()
drivers, cards = r["drivers"], r["explanation_cards"]

st.subheader("Drivers")
trig = [d for d in drivers if d.triggered]
if not trig:
    st.success("No risk drivers were triggered by the current thresholds.")
for d in trig:
    with st.container(border=True):
        st.markdown(f"**Driver {d.code}: {d.name}** (triggered)")
        st.write(d.narrative)
        st.caption(f"Evidence: {d.evidence}")
rest = [d for d in drivers if not d.triggered and d.assessable]
if rest:
    with st.expander(f"Checked but not triggered ({len(rest)})"):
        for d in rest:
            st.markdown(f"- **{d.code} {d.name}**: evidence `{d.evidence}`")
skipped = [d for d in drivers if not d.assessable]
if skipped:
    with st.expander(f"Could not be assessed with this file ({len(skipped)})", expanded=True):
        for d in skipped:
            st.markdown(f"- **{d.code} {d.name}**: needs {d.needs}.")

st.subheader("Finding \u2192 Evidence \u2192 Driver \u2192 Impact \u2192 Recommendation")
if not cards:
    st.info("No explanation cards: indicators are within acceptable ranges.")
for c in cards:
    with st.container(border=True):
        st.markdown(f"**Finding:** {c.finding}")
        st.markdown(f"**Evidence:** {c.evidence}")
        st.markdown(f"**Driver:** {c.driver}")
        st.markdown(f"**Impact:** {c.impact}")
        st.markdown(f"**Recommendation:** {c.recommendation}")
