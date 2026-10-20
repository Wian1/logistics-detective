"""Value normalisation so that values from different files compare like-for-like."""

import math
import re
from datetime import date, datetime, timedelta

import pandas as pd

from .config import DATE, TEXT, WEIGHT

_WS = re.compile(r"\s+")
_EXCEL_EPOCH = datetime(1899, 12, 30)


def is_blank(value) -> bool:
    if value is None:
        return True
    if isinstance(value, float) and math.isnan(value):
        return True
    if value is pd.NaT:
        return True
    return isinstance(value, str) and value.strip() == ""


def header(value) -> str:
    if is_blank(value):
        return ""
    return _WS.sub(" ", str(value)).strip().upper().rstrip(".").strip()


def _as_text(value) -> str:
    # Avoid "1234.0" when Excel stores an integer-like code as a number.
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    return _WS.sub(" ", str(value)).strip()


def bag_id(value) -> str | None:
    return None if is_blank(value) else _as_text(value).upper()


def text(value) -> str | None:
    return None if is_blank(value) else _as_text(value).upper()


def to_date(value):
    """Return a ``date``; unparseable input is returned as text so it still shows up."""
    if is_blank(value):
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, (int, float)):
        return (_EXCEL_EPOCH + timedelta(days=math.floor(value))).date()
    s = _as_text(value)
    try:
        return (_EXCEL_EPOCH + timedelta(days=math.floor(float(s)))).date()
    except ValueError:
        pass
    for fmt in ("%Y/%m/%d", "%Y-%m-%d", "%d/%m/%Y", "%Y/%m/%d %H:%M", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return s


def weight(value):
    """Return a float rounded to 6 dp (strips storage noise like 2009.9999999999998)."""
    if is_blank(value):
        return None
    try:
        return round(float(str(value).replace(",", "").strip()), 6)
    except ValueError:
        return _as_text(value)


NORMALISERS = {TEXT: text, DATE: to_date, WEIGHT: weight}


def display(value) -> str:
    if value is None:
        return ""
    if isinstance(value, float):
        return str(int(value)) if value.is_integer() else f"{value:g}"
    if isinstance(value, date):
        return value.isoformat()
    return str(value)
