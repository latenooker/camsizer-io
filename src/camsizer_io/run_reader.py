"""Group per-size-definition CAMSIZER exports into whole measurements.

A CAMSIZER X2 measurement with several size definitions active writes one
export file per definition, all sharing the same ``<date>_<time>_<seq>``
filename suffix. This module discovers those siblings, parses each with
:func:`camsizer_io.read_csv`, and assembles them into a
:class:`~camsizer_io.models.MeasurementRun`.
"""

from __future__ import annotations

import re

# Canonical size-definition keys, in physical/reporting order. (Task 3 will
# switch this to a re-import from camsizer_io.models.)
SIZE_DEF_ORDER: tuple[str, ...] = ("xc_min", "x_area", "xFe_max", "xFe_min", "xMa_min")

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
