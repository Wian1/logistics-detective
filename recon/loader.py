"""Read an uploaded file, locate its header row and extract the configured columns."""

import io
from dataclasses import dataclass, field

import pandas as pd

from . import normalise
from .config import Route, Source

HEADER_SCAN_ROWS = 50


class LoadError(Exception):
    pass


@dataclass
class LoadedSource:
    source: Source
    sheet: str
    header_row: int  # 1-based Excel row number
    # Columns: "Bag ID", "Excel Row", then one column per route field (normalised values)
    data: pd.DataFrame
    blank_id_rows: list[int] = field(default_factory=list)


def _read_sheets(name: str, content: bytes) -> dict[str, pd.DataFrame]:
    buf = io.BytesIO(content)
    if name.lower().endswith(".csv"):
        return {"(csv)": pd.read_csv(buf, header=None, dtype=object, keep_default_na=False)}
    return pd.read_excel(buf, sheet_name=None, header=None, dtype=object, engine="openpyxl")


def _find_header(raw: pd.DataFrame, aliases: tuple[str, ...]) -> tuple[int, list[str]] | None:
    for i in range(min(HEADER_SCAN_ROWS, len(raw))):
        headers = [normalise.header(v) for v in raw.iloc[i].tolist()]
        if any(a in headers for a in aliases):
            return i, headers
    return None


def _col_index(headers: list[str], aliases: tuple[str, ...]) -> int | None:
    for alias in aliases:
        if alias in headers:
            return headers.index(alias)  # left-most occurrence
    return None


def load_source(route: Route, source: Source, name: str, content: bytes) -> LoadedSource:
    try:
        sheets = _read_sheets(name, content)
    except Exception as exc:
        raise LoadError(f"{source.label}: could not read '{name}' ({exc}).") from exc

    found = None
    for sheet_name, raw in sheets.items():
        hit = _find_header(raw, source.key_aliases)
        if hit:
            found = (sheet_name, raw, *hit)
            break
    if not found:
        raise LoadError(
            f"{source.label}: no header row containing "
            f"{' / '.join(source.key_aliases)} found in the first {HEADER_SCAN_ROWS} rows of '{name}'."
        )
    sheet_name, raw, hdr_idx, headers = found

    key_col = _col_index(headers, source.key_aliases)
    col_map, missing = {}, []
    for f in route.fields:
        aliases = f.columns.get(source.key)
        if aliases is None:
            continue
        idx = _col_index(headers, aliases)
        if idx is None:
            missing.append(f"{f.name} (expected: {' / '.join(aliases)})")
        else:
            col_map[f.name] = (f, idx)
    if missing:
        found_headers = ", ".join(h for h in headers if h)
        raise LoadError(
            f"{source.label}: missing column(s) in '{name}': {'; '.join(missing)}. "
            f"Headers found: {found_headers}"
        )

    body = raw.iloc[hdr_idx + 1:]
    records, blank_rows = [], []
    for row_idx, row in body.iterrows():
        excel_row = int(row_idx) + 1
        values = {f.name: normalise.NORMALISERS[f.kind](row.iloc[i]) for f, i in col_map.values()}
        bag = normalise.bag_id(row.iloc[key_col])
        if bag is None:
            if any(v is not None for v in values.values()):
                blank_rows.append(excel_row)
            continue
        records.append({"Bag ID": bag, "Excel Row": excel_row, **values})

    # object dtype keeps None as None (a float column would turn it into NaN, and NaN != NaN)
    data = pd.DataFrame(records, columns=["Bag ID", "Excel Row", *col_map], dtype=object)
    return LoadedSource(source, sheet_name, hdr_idx + 1, data, blank_rows)
