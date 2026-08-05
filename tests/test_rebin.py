"""Tests for mass-conserving Q3 re-binning against the real P_01 xc_min run."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from camsizer_io import log_edges, read_csv, rebin

FIXTURE = Path(__file__).parent / "fixtures" / "P_01_cs_xc_min_20260804_180031_003.xle"


@pytest.fixture
def run():
    return read_csv(FIXTURE)


def test_log_edges_shape_and_endpoints():
    e = log_edges(0.1, 10.0, 100)
    assert e.shape == (101,)
    assert e[0] == pytest.approx(0.1)
    assert e[-1] == pytest.approx(10.0)
    # geometric spacing: constant ratio between successive edges
    ratios = e[1:] / e[:-1]
    assert np.allclose(ratios, ratios[0])


def test_log_edges_validates():
    with pytest.raises(ValueError):
        log_edges(0.0, 10.0, 10)     # non-positive lower
    with pytest.raises(ValueError):
        log_edges(10.0, 1.0, 10)     # max <= min
    with pytest.raises(ValueError):
        log_edges(0.1, 10.0, 0)      # n_bins < 1


def test_rebin_row_count_and_columns(run):
    edges = log_edges(0.08, 20.0, 100)
    df = rebin(run, edges)
    assert len(df) == 100
    assert list(df.columns) == [
        "bin_lower", "bin_upper", "bin_center", "p3", "Q3", "density"
    ]
    # bin_center is the geometric mean of the edges
    assert np.allclose(df["bin_center"], np.sqrt(df["bin_lower"] * df["bin_upper"]))


def test_rebin_conserves_mass(run):
    # A grid spanning the full populated range recovers ~100% of the volume.
    df = rebin(run, log_edges(0.01, 30.0, 300))
    assert df["p3"].sum() == pytest.approx(100.0, abs=1e-6)
    # Cumulative Q3 is monotonic and ends at 100%.
    assert np.all(np.diff(df["Q3"]) >= -1e-9)
    assert df["Q3"].iloc[-1] == pytest.approx(100.0, abs=1e-6)


def test_rebin_density_integrates_to_fraction(run):
    # density is p3 per log10(size): density * dlog10 == p3, exactly.
    df = rebin(run, log_edges(0.08, 20.0, 100))
    dlog10 = np.log10(df["bin_upper"]) - np.log10(df["bin_lower"])
    assert np.allclose(df["density"] * dlog10, df["p3"])


def test_rebin_median_matches_reported_x50(run):
    # Interpolating D50 from the re-binned cumulative curve reproduces x50.
    df = rebin(run, log_edges(0.05, 20.0, 200))
    d50 = float(np.interp(50.0, df["Q3"], df["bin_upper"]))
    assert d50 == pytest.approx(run.summary["x50"], rel=0.03)


def test_rebin_validates_edges(run):
    with pytest.raises(ValueError):
        rebin(run, [1.0])                 # fewer than two edges
    with pytest.raises(ValueError):
        rebin(run, [0.5, 0.5, 1.0])       # not strictly increasing
    with pytest.raises(ValueError):
        rebin(run, [-1.0, 1.0, 2.0])      # non-positive edge
