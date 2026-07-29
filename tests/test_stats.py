"""Tests for Folk & Ward statistics against the OK_sand_2_005 run."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from camsizer_io import folk_ward, percentile_mm, read_csv

FIXTURE = Path(__file__).parent / "fixtures" / "OK_sand_2_005.csv"


@pytest.fixture
def run():
    return read_csv(FIXTURE)


def test_interpolated_median_matches_reported_x50(run):
    # Interpolating D50 from the Q3 curve should closely match the software's x50.
    d50 = percentile_mm(run, 50)
    assert d50 == pytest.approx(run.summary["x50"], rel=0.05)


def test_interpolated_percentiles_bracket_x10_x90(run):
    assert percentile_mm(run, 10) == pytest.approx(run.summary["x10"], rel=0.08)
    assert percentile_mm(run, 90) == pytest.approx(run.summary["x90"], rel=0.08)


def test_folk_ward_well_sorted_sand(run):
    fw = folk_ward(run)
    # OK_sand is a clean, well-sorted medium sand: median ~0.31 mm ~= 1.7 phi.
    assert fw.median_phi == pytest.approx(-np.log2(run.summary["x50"]), abs=0.15)
    # Sorting for a well-sorted sand is small (Folk & Ward < ~0.5 phi).
    assert 0.0 < fw.sorting_phi < 0.7
    # Percentile diameters are returned in ascending phi (descending mm) order.
    assert fw.d_mm["d5"] > fw.d_mm["d95"]
