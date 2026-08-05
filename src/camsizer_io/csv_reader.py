"""Reliable reader for CAMSIZER X2 CSV exports.

The CAMSIZER X2 software exports a tab-delimited, UTF-16LE, CRLF-terminated
text file. It has three regions:

1. A one-line header (raw-data file, method file, size model, date, time,
   duration).
2. A block of ``label <TAB> value`` summary rows (x10/x50/x90, SPAN3, U3,
   percentile-shape values, and shape means).
3. A per-size-class table introduced by a row beginning ``Size class``.

This module parses all three into a :class:`~camsizer_io.models.CamsizerRun`.
Unlike the ``.rdf``/``.cdf``/``.xConAlp`` binaries, the CSV export is a
documented, stable text format, so this path is the supported one.
"""

from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

from .models import CamsizerRun, RunMeta

# Maps a normalized summary label to the key used in CamsizerRun.summary.
_SUMMARY_KEYS: dict[str, str] = {
    "x [mm] at Q3 = 10.0 %": "x10",
    "x [mm] at Q3 = 50.0 %": "x50",
    "x [mm] at Q3 = 90.0 %": "x90",
    "SPAN3": "SPAN3",
    "U3": "U3",
    "Mean value SPHT3": "mean_SPHT3",
    "Mean value Symm3": "mean_Symm3",
    "Mean value b/l3": "mean_b_l3",
}

_TABLE_COLUMNS = ["bin_lower", "bin_upper", "p3", "Q3", "SPHT3", "Symm3", "b_l3", "PDN"]


def _to_float(text: str) -> float | None:
    """Parse a CAMSIZER numeric cell, tolerating comma decimals and blanks.

    Args:
        text: Raw cell text.

    Returns:
        The parsed float, or ``None`` if the cell is not numeric.
    """
    text = text.strip().replace(",", ".")
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def read_csv(path: str | Path) -> CamsizerRun:
    """Read a CAMSIZER X2 CSV export into a :class:`CamsizerRun`.

    Args:
        path: Path to the ``.csv``, ``.xle``, or ``.xld`` export (UTF-16LE,
            tab-delimited; identical format).

    Returns:
        A populated :class:`CamsizerRun` with ``meta``, ``psd`` and
        ``summary``.

    Raises:
        FileNotFoundError: If ``path`` does not exist.
        ValueError: If no size-class table is found in the file.
    """
    path = Path(path)
    text = path.read_text(encoding="utf-16")
    lines = text.replace("\r\n", "\n").split("\n")
    rows = [line.split("\t") for line in lines]

    meta = _parse_header(rows)
    summary = _parse_summary(rows)
    psd = _parse_table(rows)

    return CamsizerRun(meta=meta, psd=psd, summary=summary, source_path=str(path))


# `.xle` (point decimal) and `.xld` (comma decimal) exports share the CSV
# export's exact three-region layout, so read_csv reads them unchanged. The
# alias documents that these are supported too.
read_export = read_csv


def _parse_header(rows: list[list[str]]) -> RunMeta:
    """Extract run metadata from the first non-empty row.

    Args:
        rows: All rows of the file, each split on tabs.

    Returns:
        A :class:`RunMeta`. Fields absent from the header are left ``None``.
    """
    for row in rows:
        cells = [c.strip() for c in row]
        if cells and cells[0]:
            padded = cells + [None] * (6 - len(cells))
            return RunMeta(
                source_file=padded[0] or None,
                method_file=padded[1] or None,
                size_model=padded[2] or None,
                date=padded[3] or None,
                time=padded[4] or None,
                duration=padded[5] or None,
            )
    return RunMeta()


def _parse_summary(rows: list[list[str]]) -> dict[str, float]:
    """Collect scalar summary values from ``label <TAB> value`` rows.

    Recognizes the fixed labels in :data:`_SUMMARY_KEYS` plus the
    ``Q3 (SPHT=0.9) [%]`` family, which is emitted verbatim as e.g.
    ``Q3_SPHT_0.9``.

    Args:
        rows: All rows of the file, each split on tabs.

    Returns:
        Mapping of summary key to value.
    """
    summary: dict[str, float] = {}
    for row in rows:
        if len(row) < 2:
            continue
        label = row[0].strip()
        value = _to_float(row[1])
        if value is None or not label:
            continue
        if label in _SUMMARY_KEYS:
            summary[_SUMMARY_KEYS[label]] = value
            continue
        m = re.match(r"Q3 \((SPHT|Symm|b/l)=([\d.]+)\) \[%\]", label)
        if m:
            desc = m.group(1).replace("/", "_")
            summary[f"Q3_{desc}_{m.group(2)}"] = value
    return summary


def _parse_table(rows: list[list[str]]) -> pd.DataFrame:
    """Parse the per-size-class table into a tidy DataFrame.

    The table starts at the row whose first cell is ``Size class`` and runs
    to the first subsequent row that does not have a numeric first cell.

    Args:
        rows: All rows of the file, each split on tabs.

    Returns:
        A DataFrame with the columns in :data:`_TABLE_COLUMNS`.

    Raises:
        ValueError: If no ``Size class`` header row is present.
    """
    start = None
    for i, row in enumerate(rows):
        if row and row[0].strip() == "Size class":
            start = i + 1
            break
    if start is None:
        raise ValueError("No 'Size class' table header found in CSV export.")

    records: list[list[float]] = []
    for row in rows[start:]:
        if len(row) < len(_TABLE_COLUMNS):
            continue
        first = _to_float(row[0])
        if first is None:
            break
        values = [_to_float(c) for c in row[: len(_TABLE_COLUMNS)]]
        if any(v is None for v in values):
            break
        records.append(values)  # type: ignore[arg-type]

    df = pd.DataFrame(records, columns=_TABLE_COLUMNS)
    df["PDN"] = df["PDN"].astype(int)
    return df
