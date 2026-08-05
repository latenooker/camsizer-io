"""Tests for Folk & Ward statistics against the OK_sand_2_005 run."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from camsizer_io import folk_ward, percentile_mm, read_csv, read_run, MeasurementRun

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


FIVE = Path(__file__).parent / "fixtures" / "P_01_cs_xc_min_20260804_180031_003.xle"


def test_folk_ward_measurement_defaults_to_xc_min():
    mrun = read_run(FIVE)
    got = folk_ward(mrun)
    ref = folk_ward(mrun["xc_min"])
    assert got.median_phi == pytest.approx(ref.median_phi, abs=1e-9)
    assert got.median_phi == pytest.approx(-0.1366, abs=1e-3)
    assert got.sorting_phi == pytest.approx(0.6598, abs=1e-3)


def test_folk_ward_measurement_size_def_override():
    mrun = read_run(FIVE)
    got = folk_ward(mrun, size_def="x_area")
    assert got.d_mm["d50"] == pytest.approx(1.3419, rel=0.05)


def test_folk_ward_measurement_missing_def_falls_back_and_warns():
    run = read_csv(Path(__file__).parent / "fixtures" / "P_01_cs_x_area_20260804_180031_003.xle")
    mrun = MeasurementRun(sample="P_01_cs", timestamp="20260804_180031",
                          seq="003", runs={"x_area": run})
    with pytest.warns(UserWarning):
        got = folk_ward(mrun)  # xc_min absent -> fall back to x_area
    assert got.d_mm["d50"] == pytest.approx(1.3419, rel=0.05)
