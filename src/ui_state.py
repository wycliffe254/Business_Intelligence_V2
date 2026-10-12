"""Small Streamlit helpers shared by pages."""
import pandas as pd
import streamlit as st

STATUS_TEXT = {"available": "Available", "derived": "Available (derived estimate)", "unavailable": "NOT available"}


def get_result():
    """Return the pipeline result stored by the main page, or stop with a friendly message."""
    r = st.session_state.get("pipeline_result")
    if r is None:
        st.warning("No dataset loaded yet. Open the main page (app) and choose a sample dataset or upload a CSV first.")
        st.stop()
    return r


def capability_table(schema) -> pd.DataFrame:
    return pd.DataFrame([{"Analysis": c.label, "Status": STATUS_TEXT[c.status], "Columns still needed": ", ".join(c.missing_columns) or "-",
                          "What it unlocks": c.unlocks} for c in schema.capabilities])


def show_completeness(result, always_table: bool = False):
    """Banner explaining which analyses are limited because columns are missing, and what to add."""
    schema = result["schema"]
    health = result["health_result"]
    guesses = {a: m[0] for a, m in schema.match_how.items() if m[1] == "keyword"}
    chosen = {a: m[0] for a, m in schema.match_how.items() if m[1] == "chosen by you"}
    plain = {a: m[0] for a, m in schema.match_how.items() if m[1] == "alias"}
    if plain:
        st.info("Recognised these headers: " + ", ".join(f"`{a}` \u2192 `{b}`" for a, b in plain.items()))
    if chosen:
        st.info("Matched as you chose: " + ", ".join(f"`{a}` \u2192 `{b}`" for a, b in chosen.items()))
    if guesses:
        st.warning("Matched by keyword (please check, and correct under 'Review how your columns were matched' if wrong): "
                   + ", ".join(f"`{a}` \u2192 `{b}`" for a, b in guesses.items()))
    if schema.missing_columns or schema.derived_columns:
        msg = schema.banner_lines()
        (st.error if schema.level == "minimal" else st.warning)(
            f"**Limited analysis \u2013 data completeness {schema.coverage_pct:.0f}%.** " + msg[0] +
            (" For a proper analysis and meaningful insights, add the columns listed below." if schema.missing_columns else ""))
        if health.partial:
            st.caption(f"Only {health.assessable_points:.0f} of the 100 Financial Health Score points could be assessed with these columns, "
                       "so the score is provisional (normalised over the assessable points).")
        with st.expander("What is missing and what each missing column would unlock", expanded=schema.level != "full" or always_table):
            for line in msg[1:]:
                st.markdown(f"- {line}")
            st.dataframe(capability_table(schema), hide_index=True)
    elif always_table:
        st.success("All expected columns are present.")
    if schema.unrecognised_columns:
        st.caption("Columns ignored by the analysis (not recognised): " + ", ".join(schema.unrecognised_columns))
