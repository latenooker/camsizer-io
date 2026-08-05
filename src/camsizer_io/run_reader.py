"""Group per-size-definition CAMSIZER exports into whole measurements.

A CAMSIZER X2 measurement with several size definitions active writes one
export file per definition, all sharing the same ``<date>_<time>_<seq>``
filename suffix. This module discovers those siblings, parses each with
:func:`camsizer_io.read_csv`, and assembles them into a
:class:`~camsizer_io.models.MeasurementRun`.
"""

from __future__ import annotations

import re
import warnings
from collections.abc import Iterable
from pathlib import Path

import pandas as pd

from .csv_reader import read_csv
from .models import CamsizerRun, MeasurementRun, SIZE_DEF_ORDER, _LONG_COLUMNS

# Filename token (as written by the software) -> canonical key, for cross-check.
_TOKEN_TO_CANONICAL: dict[str, str] = {
    "xc_min": "xc_min",
    "x_area": "x_area",
    "xFemax": "xFe_max",
    "xFemin": "xFe_min",
    "xMamin": "xMa_min",
}

# <sample ending in _cs>_<token>_<8-digit date>_<6-digit time>_<seq>.<ext>
_RUN_FILENAME_RE = re.compile(
    r"^(?P<sample>.+?_cs)_(?P<token>.+?)_(?P<date>\d{8})_(?P<time>\d{6})_(?P<seq>\d+)$"
)


def _parse_run_filename(name: str) -> tuple[str, str, str, str, str]:
    """Split a CAMSIZER export filename into its run-identity fields.

    Args:
        name: File name (with or without extension), e.g.
            ``P_01_cs_x_area_20260804_180031_003.xle``.

    Returns:
        ``(sample, size_token, date, time, seq)``.

    Raises:
        ValueError: If ``name`` does not match the run filename pattern.
    """
    stem = name.rsplit(".", 1)[0]
    m = _RUN_FILENAME_RE.match(stem)
    if m is None:
        raise ValueError(f"Not a CAMSIZER run filename: {name!r}")
    return (
        m.group("sample"),
        m.group("token"),
        m.group("date"),
        m.group("time"),
        m.group("seq"),
    )


def _canonical_size_def(size_model: str | None) -> str:
    """Return the canonical size-definition key from a header ``size_model``.

    Args:
        size_model: Header string, e.g. ``xc_min with shape parameter 1.0000``.

    Returns:
        The leading token, e.g. ``xc_min``.

    Raises:
        ValueError: If ``size_model`` is ``None`` or empty.
    """
    if not size_model:
        raise ValueError("Cannot derive size definition from empty size_model.")
    return size_model.split()[0].strip()


def read_run(path: str | Path) -> MeasurementRun:
    """Assemble a :class:`MeasurementRun` from any one of its export files.

    Given one size-definition export, this finds the sibling files that share
    its ``(sample, date, time, seq)`` identity, parses each, and groups them by
    canonical size definition (taken from each file's header ``size_model``).

    Args:
        path: Path to any one of the run's export files (e.g. an ``.xle``).

    Returns:
        A :class:`MeasurementRun` holding every size definition found.

    Raises:
        FileNotFoundError: If ``path`` does not exist.
        ValueError: If ``path``'s name is not a CAMSIZER run filename.

    Warnings:
        UserWarning: If fewer than five size definitions are found, if a
        filename token disagrees with its header, or on a duplicate definition.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(path)
    sample, _token, date, time, seq = _parse_run_filename(path.name)

    runs: dict[str, CamsizerRun] = {}
    for sibling in sorted(path.parent.glob(f"*{path.suffix}")):
        try:
            s_sample, s_token, s_date, s_time, s_seq = _parse_run_filename(sibling.name)
        except ValueError:
            continue
        if (s_sample, s_date, s_time, s_seq) != (sample, date, time, seq):
            continue
        run = read_csv(sibling)
        canon = _canonical_size_def(run.meta.size_model)
        expected = _TOKEN_TO_CANONICAL.get(s_token)
        if expected is not None and expected != canon:
            warnings.warn(
                f"{sibling.name}: filename token {s_token!r} implies {expected!r} "
                f"but header says {canon!r}; trusting header.",
                UserWarning,
                stacklevel=2,
            )
        if canon in runs:
            warnings.warn(
                f"Duplicate size definition {canon!r} in run "
                f"{sample}_{date}_{time}_{seq}; keeping {sibling.name}.",
                UserWarning,
                stacklevel=2,
            )
        runs[canon] = run

    if len(runs) < len(SIZE_DEF_ORDER):
        warnings.warn(
            f"Run {sample}_{date}_{time}_{seq}: found {len(runs)} size "
            f"definition(s) {sorted(runs)}, expected {len(SIZE_DEF_ORDER)}.",
            UserWarning,
            stacklevel=2,
        )

    return MeasurementRun(
        sample=sample,
        timestamp=f"{date}_{time}",
        seq=seq,
        runs=runs,
        source_dir=str(path.parent),
    )


def read_batch(directory: str | Path, pattern: str = "*.xle") -> list[MeasurementRun]:
    """Group every matching export in a directory into measurements.

    Args:
        directory: Directory to scan.
        pattern: Glob for the export files (default ``*.xle``; use ``*.xld`` or
            ``*.csv`` for other export variants).

    Returns:
        One :class:`MeasurementRun` per ``(sample, date, time, seq)`` group,
        sorted by ``(sample, timestamp, seq)``. Files that do not match the run
        filename pattern are ignored.
    """
    directory = Path(directory)
    groups: dict[tuple[str, str, str, str], Path] = {}
    for f in sorted(directory.glob(pattern)):
        try:
            sample, _token, date, time, seq = _parse_run_filename(f.name)
        except ValueError:
            continue
        groups.setdefault((sample, date, time, seq), f)
    runs = [read_run(anchor) for anchor in groups.values()]
    return sorted(runs, key=lambda r: (r.sample, r.timestamp, r.seq))


def to_long(runs: MeasurementRun | Iterable[MeasurementRun]) -> pd.DataFrame:
    """Concatenate one or more measurements into a single tidy long table.

    Args:
        runs: A single :class:`MeasurementRun` or an iterable of them.

    Returns:
        The vertical concatenation of each run's :meth:`MeasurementRun.to_long`.
    """
    if isinstance(runs, MeasurementRun):
        return runs.to_long()
    frames = [r.to_long() for r in runs]
    if not frames:
        return pd.DataFrame(columns=_LONG_COLUMNS)
    return pd.concat(frames, ignore_index=True)
