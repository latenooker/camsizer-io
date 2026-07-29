"""Folk & Ward graphical grain-size statistics from a CAMSIZER run.

Percentiles are interpolated from the cumulative ``Q3`` curve in the parsed
size-class table (using each class's upper edge as the size at that cumulative
percent), then converted to phi units (``phi = -log2(mm)``). The classic
Folk & Ward (1957) graphical measures are computed from the phi percentiles.

These reproduce the *volume/area-weighted* (``Q3``) distribution the CAMSIZER
reports, not a number-weighted one.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .models import CamsizerRun


@dataclass
class FolkWard:
    """Folk & Ward (1957) graphical grain-size statistics, in phi units.

    Attributes:
        mean_phi: Graphic mean ``(phi16 + phi50 + phi84) / 3``.
        median_phi: Median grain size ``phi50``.
        sorting_phi: Inclusive graphic standard deviation (sorting).
        skewness: Inclusive graphic skewness (dimensionless).
        kurtosis: Graphic kurtosis (dimensionless).
        d_mm: Selected percentile diameters in mm, keyed ``d5``..``d95`` using
            the Folk & Ward "percent coarser" convention (``d5`` is the coarse
            end, ``d95`` the fine end).
    """

    mean_phi: float
    median_phi: float
    sorting_phi: float
    skewness: float
    kurtosis: float
    d_mm: dict[str, float]


def _mm_to_phi(mm: float) -> float:
    """Convert a diameter in millimetres to phi units.

    Args:
        mm: Diameter in millimetres (> 0).

    Returns:
        The phi value ``-log2(mm)``.
    """
    return float(-np.log2(mm))


def percentile_mm(run: CamsizerRun, pct: float) -> float:
    """Interpolate the grain diameter (mm) at a cumulative ``Q3`` percentile.

    Args:
        run: A parsed :class:`CamsizerRun`.
        pct: Cumulative percent passing (0-100), e.g. ``50`` for the median.

    Returns:
        The interpolated diameter in millimetres.

    Raises:
        ValueError: If the run has no usable ``Q3`` curve.
    """
    df = run.psd
    if df.empty or "Q3" not in df:
        raise ValueError("Run has no Q3 size-class table to interpolate.")
    q3 = df["Q3"].to_numpy(dtype=float)
    x = df["bin_upper"].to_numpy(dtype=float)
    # Keep the strictly-increasing portion of the cumulative curve so np.interp
    # (which requires increasing xp) is well defined across the populated range.
    keep = np.concatenate([[True], np.diff(q3) > 0])
    q3k, xk = q3[keep], x[keep]
    if len(q3k) < 2:
        raise ValueError("Q3 curve is degenerate; cannot interpolate percentiles.")
    return float(np.interp(pct, q3k, xk))


def folk_ward(run: CamsizerRun) -> FolkWard:
    """Compute Folk & Ward graphical statistics for a run.

    Args:
        run: A parsed :class:`CamsizerRun`.

    Returns:
        A :class:`FolkWard` of phi-based statistics and the percentile
        diameters used.

    Raises:
        ValueError: If percentiles cannot be interpolated from the run.
    """
    # Folk & Ward percentiles are defined as "percent coarser", whereas the
    # CAMSIZER Q3 curve is "percent finer (passing)". The p-th coarser
    # percentile is therefore read at Q3 = (100 - p) percent passing. This makes
    # phi increase with p (phi5 < phi16 < ... < phi95) as the formulas require.
    pcts = [5, 16, 25, 50, 75, 84, 95]
    d_mm = {f"d{p}": percentile_mm(run, 100 - p) for p in pcts}
    phi = {p: _mm_to_phi(d_mm[f"d{p}"]) for p in pcts}

    mean_phi = (phi[16] + phi[50] + phi[84]) / 3.0
    sorting = (phi[84] - phi[16]) / 4.0 + (phi[95] - phi[5]) / 6.6
    denom_84_16 = phi[84] - phi[16]
    denom_95_5 = phi[95] - phi[5]
    skew = (phi[16] + phi[84] - 2 * phi[50]) / (2 * denom_84_16) + (
        phi[5] + phi[95] - 2 * phi[50]
    ) / (2 * denom_95_5)
    kurt = denom_95_5 / (2.44 * (phi[75] - phi[25]))

    return FolkWard(
        mean_phi=mean_phi,
        median_phi=phi[50],
        sorting_phi=sorting,
        skewness=float(skew),
        kurtosis=float(kurt),
        d_mm=d_mm,
    )
