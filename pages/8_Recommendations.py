import pandas as pd
import streamlit as st
from src.ui_state import get_result

st.set_page_config(page_title="Recommendations", layout="wide")
st.title("Management Recommendations")
r = get_result()
recs = r["recommendations"]
st.caption("Each recommendation follows: observed issue \u2192 evidence \u2192 management action, and exists only because a driver was triggered. "
           "They are decision-support suggestions ranked by analytical priority, not guarantees.")
if not recs:
    st.success("No priority recommendations: current indicators are within acceptable ranges.")
for x in recs:
    with st.container(border=True):
        st.markdown(f"### Priority {x.priority}: {x.title}  \n*Category: {x.category}*")
        st.markdown(f"**Observed issue:** {x.observed_issue}")
        st.markdown(f"**Evidence:** {x.evidence}")
        st.markdown(f"**Management action:** {x.management_action}")
if recs:
    st.download_button("Recommendations (CSV)", pd.DataFrame([x.__dict__ for x in recs]).to_csv(index=False).encode("utf-8"), "recommendations.csv", "text/csv")
