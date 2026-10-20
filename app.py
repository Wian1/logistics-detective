"""Logistics Detective - bag reconciliation across WIRE and partner files.

Run with:  streamlit run app.py
"""

import numpy as np
import pandas as pd
import streamlit as st

from recon import ROUTES, LoadError, load_source, reconcile
from recon.templates import build_template

st.set_page_config(page_title="Logistics Detective", page_icon="🔍", layout="wide")


@st.cache_data(show_spinner="Reconciling...")
def run(route_name: str, files: tuple[tuple[str, str, bytes], ...]):
    route = ROUTES[route_name]
    by_key = {key: (name, content) for key, name, content in files}
    loaded = [load_source(route, s, *by_key[s.key]) for s in route.sources]
    meta = [(ls.source.label, ls.sheet, ls.header_row, len(ls.data)) for ls in loaded]
    return reconcile(route, loaded), meta


def table(df: pd.DataFrame, filename: str, key: str, styler=None):
    if df.empty:
        st.success("Nothing to report.")
        return
    st.dataframe(styler if styler is not None else df, hide_index=True, width="stretch")
    st.download_button(
        "Download CSV", df.to_csv(index=False).encode("utf-8-sig"),
        file_name=filename, mime="text/csv", key=key,
    )


# --- Sidebar ----------------------------------------------------------------
with st.sidebar:
    st.title("🔍 Logistics Detective")
    route_name = st.radio("Route", list(ROUTES))
    route = ROUTES[route_name]
    st.caption(route.description)
    st.markdown("**Validated fields**")
    st.markdown("\n".join(f"- {f.name}" for f in route.fields))
    st.caption(
        "WIRE is the reference: its bag IDs are treated as correct. "
        "Weights must match exactly; dates are compared on the calendar day; text ignores case."
    )

# --- Uploads ----------------------------------------------------------------
st.header(route.name)
cols = st.columns(len(route.sources))
uploads = {}
for col, src in zip(cols, route.sources):
    with col:
        uploads[src.key] = st.file_uploader(
            f"{src.label} file" + (" (reference)" if src.is_reference else ""),
            type=["xlsx", "xlsm", "csv"], key=f"{route_name}-{src.key}",
        )
        if route.offers_templates:
            st.download_button(
                f"Download {src.label} template", build_template(route, src),
                file_name=f"{src.label.upper()}_TEMPLATE.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key=f"tpl-{route_name}-{src.key}",
                help="Blank sheet with the expected headers. Paste the source columns in, save, then upload it here.",
            )

ready = all(uploads.values())
# Keep results on screen across reruns (filters/toggles) until the route or files change.
signature = (route_name, tuple(f.file_id for f in uploads.values())) if ready else None
if st.button("Run reconciliation", type="primary", disabled=not ready):
    st.session_state["ran"] = signature
if not ready or st.session_state.get("ran") != signature:
    st.info("Upload all files, then run the reconciliation." if not ready else "Ready - click Run reconciliation.")
    st.stop()

files = tuple((k, f.name, f.getvalue()) for k, f in uploads.items())
try:
    result, meta = run(route_name, files)
except LoadError as exc:
    st.error(str(exc))
    st.stop()

with st.expander("Files read"):
    st.dataframe(
        pd.DataFrame(meta, columns=["File", "Sheet", "Header row", "Rows with bag ID"]),
        hide_index=True,
    )

# --- Summary ----------------------------------------------------------------
items = list(result.summary.items())
for start in range(0, len(items), 4):
    for c, (label, value) in zip(st.columns(4), items[start:start + 4]):
        c.metric(label, f"{value:,}")

slug = route_name.lower().replace(" ", "_")
tabs = st.tabs([
    f"Missing bags ({len(result.missing):,})",
    f"Field mismatches ({len(result.mismatches):,})",
    f"Full comparison ({len(result.comparison):,})",
    f"Data quality ({len(result.quality):,})",
])

with tabs[0]:
    st.caption("Bags that appear in at least one file but not in all of them.")
    table(result.missing, f"{slug}_missing_bags.csv", "dl-missing")

with tabs[1]:
    st.dataframe(result.field_counts, hide_index=True)
    mm = result.mismatches
    if not mm.empty:
        chosen = st.multiselect("Filter by field", sorted(mm["Field"].unique()))
        if chosen:
            mm = mm[mm["Field"].isin(chosen)]
    table(mm, f"{slug}_field_mismatches.csv", "dl-mismatch")

with tabs[2]:
    st.caption("Every bag that is in WIRE and at least one other file. Highlighted cells disagree with WIRE.")
    comp = result.comparison
    only_bad = st.toggle("Show only bags with mismatches")
    mask = result.mismatch_mask
    if only_bad:
        keep = comp["Mismatched Fields"].astype(bool)
        comp, mask = comp[keep], mask[keep]
    highlight = np.where(mask.values.astype(bool), "background-color: rgba(255, 75, 75, 0.25)", "")
    styler = comp.style.apply(lambda _: highlight, axis=None)
    table(comp, f"{slug}_full_comparison.csv", "dl-comp", styler=styler)

with tabs[3]:
    st.caption("Blank IDs, duplicates within a file, and IDs that don't follow the KxWx_xxxxx_xxxx format.")
    table(result.quality, f"{slug}_data_quality.csv", "dl-quality")
