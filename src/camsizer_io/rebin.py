"""Mass-conserving re-binning of a CAMSIZER volume distribution.

The CAMSIZER reports the volume distribution on a fixed, often very fine set of
size classes (e.g. ~1000 log-spaced classes). For plotting a readable density
(a PDF) or for comparing runs measured with different class files, it is useful
to re-bin onto a coarser, common grid. Because the re-binning is done from the
*cumulative* ``Q3`` curve — the volume fraction in an output bin is the exact
``Q3`` increment across that bin — no volume is created or destroyed: it is a
mass-conserving interpolation, not a histogram re-assignment.

Only the size distribution is re-binned; class-mean shape characteristics
(``SPHT3`` etc.) are not (re-binning them would require volume-weighted
averaging) and are intentionally out of scope here.
"""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np
import pandas as pd

from .models import CamsizerRun

_REBIN_COLUMNS = ["bin_lower", "bin_upper", "bin_center", "p3", "Q3", "density"]


def log_edges(x_min: float, x_max: float, n_bins: int) -> np.ndarray:
    """Return ``n_bins + 1`` logarithmically-spaced size-class edges.

    Args:
        x_min: Lower edge of the first bin (mm, > 0).
        x_max: Upper edge of the last bin (mm, > ``x_min``).
        n_bins: Number of bins (>= 1); the result has ``n_bins + 1`` edges.

    Returns:
        A 1-D array of ``n_bins + 1`` edges geometrically spaced from ``x_min``
        to ``x_max`` (constant size ratio per bin).

    Raises:
        ValueError: If ``x_min <= 0``, ``x_max <= x_min``, or ``n_bins < 1``.
    """
    if x_min <= 0:
        raise ValueError("x_min must be positive for a log-spaced grid.")
    if x_max <= x_min:
        raise ValueError("x_max must be greater than x_min.")
    if n_bins < 1:
        raise ValueError("n_bins must be at least 1.")
    return np.geomspace(x_min, x_max, n_bins + 1)


def rebin(run: CamsizerRun, edges: Sequence[float]) -> pd.DataFrame:
    """Re-bin a run's volume distribution onto arbitrary size-class edges.

    The output volume fraction ``p3`` in each bin is the exact increment of the
    run's cumulative ``Q3`` curve across that bin (linear interpolation of
    ``Q3`` in size), so mass is conserved. ``density`` is ``p3`` normalized per
    ``log10`` size interval — the natural PDF for a log size axis, where the
    area under the curve (in ``log10`` size) equals the covered volume percent.

    Args:
        run: A parsed :class:`~camsizer_io.CamsizerRun` (its ``psd`` supplies
            ``bin_upper`` and cumulative ``Q3``).
        edges: A strictly increasing sequence of positive size-class edges
            (mm), length ``>= 2``. Use :func:`log_edges` to build a log grid.

    Returns:
        A DataFrame with one row per output bin and columns
        ``bin_lower``, ``bin_upper``, ``bin_center`` (geometric mean of the
        edges), ``p3`` (volume % in the bin), ``Q3`` (cumulative volume % at
        ``bin_upper``, measured from size 0), and ``density`` (``p3`` per
        ``log10`` mm). ``p3`` sums to the ``Q3`` span the grid covers; a grid
        spanning the full populated range recovers ~100%.

    Raises:
        ValueError: If ``edges`` has fewer than two values, is not strictly
            increasing, contains a non-positive value, or if ``run`` has no
            usable ``Q3`` table.
    """
    e = np.asarray(edges, dtype=float)
    if e.ndim != 1 or e.size < 2:
        raise ValueError("edges must be a 1-D sequence of at least two values.")
    if np.any(e <= 0):
        raise ValueError("all edges must be positive (log-size grid).")
    if np.any(np.diff(e) <= 0):
        raise ValueError("edges must be strictly increasing.")

    psd = run.psd
    if psd.empty or "Q3" not in psd or "bin_upper" not in psd:
        raise ValueError("run has no Q3 size-class table to re-bin.")

    x = psd["bin_upper"].to_numpy(dtype=float)
    q3 = psd["Q3"].to_numpy(dtype=float)
    q3_at_edges = np.interp(e, x, q3, left=0.0, right=100.0)

    lo, hi = e[:-1], e[1:]
    p3 = np.diff(q3_at_edges)
    density = p3 / (np.log10(hi) - np.log10(lo))
    return pd.DataFrame(
        {
            "bin_lower": lo,
            "bin_upper": hi,
            "bin_center": np.sqrt(lo * hi),
            "p3": p3,
            "Q3": q3_at_edges[1:],
            "density": density,
        }
    )
