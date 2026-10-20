"""Compare loaded sources against the WIRE reference."""

import re
from dataclasses import dataclass

import pandas as pd

from . import normalise
from .config import BAG_ID_PATTERN, Route
from .loader import LoadedSource

PRESENT, ABSENT = "✓", "✗"
NOT_IN_FILE = "(bag not in file)"
_ID_RE = re.compile(BAG_ID_PATTERN)


@dataclass
class Result:
    summary: dict[str, int]
    field_counts: pd.DataFrame  # Field, mismatching file, count
    missing: pd.DataFrame       # bags absent from at least one file
    mismatches: pd.DataFrame    # long: one row per bag x field that disagrees
    comparison: pd.DataFrame    # wide: every bag in WIRE + at least one other file
    mismatch_mask: pd.DataFrame  # same shape as comparison, True where a cell disagrees
    quality: pd.DataFrame       # duplicates, blank IDs, bad-format IDs


def _quality(loaded: list[LoadedSource]) -> pd.DataFrame:
    rows = []
    for ls in loaded:
        label, df = ls.source.label, ls.data
        for r in ls.blank_id_rows:
            rows.append((label, "Blank bag ID", "", f"Excel row {r}"))
        for bag, grp in df[df["Bag ID"].duplicated(keep=False)].groupby("Bag ID"):
            rows_txt = ", ".join(str(r) for r in grp["Excel Row"])
            rows.append((label, "Duplicate bag ID (first occurrence used)", bag, f"Excel rows {rows_txt}"))
        for _, rec in df[~df["Bag ID"].str.match(_ID_RE)].iterrows():
            rows.append((label, "Bag ID not in KxWx_xxxxx_xxxx format", rec["Bag ID"], f"Excel row {rec['Excel Row']}"))
    return pd.DataFrame(rows, columns=["File", "Issue", "Bag ID", "Location"])


def reconcile(route: Route, loaded: list[LoadedSource]) -> Result:
    ref_label = route.reference.label
    labels = [ls.source.label for ls in loaded]
    others = [l for l in labels if l != ref_label]
    tables = {ls.source.label: ls.data.drop_duplicates("Bag ID").set_index("Bag ID") for ls in loaded}
    ids = {l: set(t.index) for l, t in tables.items()}
    all_ids = sorted(set().union(*ids.values()))

    # --- Presence -----------------------------------------------------------
    missing_rows = []
    for bag in all_ids:
        flags = {l: bag in ids[l] for l in labels}
        if all(flags.values()):
            continue
        if not flags[ref_label]:
            found_in = ", ".join(l for l in labels if flags[l])
            status = f"Not in {ref_label} (possible mistyped ID) - found in {found_in}"
        else:
            status = "Missing from " + ", ".join(l for l in labels if not flags[l])
        missing_rows.append({"Bag ID": bag, **{l: PRESENT if flags[l] else ABSENT for l in labels}, "Status": status})
    missing = pd.DataFrame(missing_rows, columns=["Bag ID", *labels, "Status"])

    # --- Field comparison ---------------------------------------------------
    matched = sorted(b for b in ids[ref_label] if any(b in ids[o] for o in others))
    comp_cols = ["Bag ID"] + [f"{f.name} | {l}" for f in route.fields for l in labels] + ["Mismatched Fields"]
    comp_rows, mask_rows, mm_rows = [], [], []
    for bag in matched:
        comp, mask, bad_fields = {"Bag ID": bag}, {"Bag ID": False}, []
        for f in route.fields:
            ref_val = tables[ref_label].at[bag, f.name]
            disagree = []
            for l in labels:
                present = bag in ids[l]
                val = tables[l].at[bag, f.name] if present else None
                comp[f"{f.name} | {l}"] = normalise.display(val) if present else NOT_IN_FILE
                is_bad = l != ref_label and present and val != ref_val
                mask[f"{f.name} | {l}"] = is_bad
                if is_bad:
                    disagree.append(l)
            if disagree:
                bad_fields.append(f.name)
                mm_rows.append({
                    "Bag ID": bag, "Field": f.name,
                    **{l: comp[f"{f.name} | {l}"] for l in labels},
                    "Disagrees with WIRE": ", ".join(disagree),
                })
        comp["Mismatched Fields"] = ", ".join(bad_fields)
        mask["Mismatched Fields"] = bool(bad_fields)
        comp_rows.append(comp)
        mask_rows.append(mask)

    comparison = pd.DataFrame(comp_rows, columns=comp_cols)
    mismatch_mask = pd.DataFrame(mask_rows, columns=comp_cols)
    mismatches = pd.DataFrame(mm_rows, columns=["Bag ID", "Field", *labels, "Disagrees with WIRE"])

    field_counts = pd.DataFrame(
        [(f.name, o, int(mismatch_mask[f"{f.name} | {o}"].sum()) if len(mismatch_mask) else 0)
         for f in route.fields for o in others],
        columns=["Field", "File", "Mismatches vs WIRE"],
    )

    summary = {f"Bags in {l}": len(ids[l]) for l in labels}
    summary["Bags in all files"] = len(set.intersection(*ids.values()))
    summary["Bags missing from a file"] = int(missing["Status"].str.startswith("Missing").sum())
    summary[f"IDs not in {ref_label}"] = int(missing["Status"].str.startswith("Not in").sum())
    summary["Bags with field mismatches"] = int(comparison["Mismatched Fields"].astype(bool).sum())

    return Result(summary, field_counts, missing, mismatches, comparison, mismatch_mask, _quality(loaded))
