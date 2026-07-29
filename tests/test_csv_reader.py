"""Tests for the reliable CSV reader against the real OK_sand_2_005 export."""

from __future__ import annotations

from pathlib import Path

import pytest

from camsizer_io import read_csv

FIXTURE = Path(__file__).parent / "fixtures" / "OK_sand_2_005.csv"


@pytest.fixture
def run():
    return read_csv(FIXTURE)


def test_meta_parsed(run):
    assert run.meta.source_file == "OK_sand_2_005.rdf"
    assert run.meta.method_file == "measure0.afg"
    assert run.meta.size_model.startswith("xc_min")
    assert run.meta.date == "2026/07/28"
    assert run.meta.duration == "0 min 19 s"


def test_summary_percentiles(run):
    # Ground-truth values read directly from the export.
    assert run.summary["x10"] == pytest.approx(0.2262, abs=1e-4)
    assert run.summary["x50"] == pytest.approx(0.3099, abs=1e-4)
    assert run.summary["x90"] == pytest.approx(0.4214, abs=1e-4)
    assert run.summary["SPAN3"] == pytest.approx(0.630, abs=1e-3)
    assert run.summary["mean_SPHT3"] == pytest.approx(0.940, abs=1e-3)


def test_psd_table_shape_and_columns(run):
    expected_cols = ["bin_lower", "bin_upper", "p3", "Q3", "SPHT3", "Symm3", "b_l3", "PDN"]
    assert list(run.psd.columns) == expected_cols
    assert len(run.psd) > 10
    # Q3 is a cumulative curve ending at 100%.
    assert run.psd["Q3"].iloc[-1] == pytest.approx(100.0, abs=1e-3)


def test_particle_count_ground_truth(run):
    # Sum of the PDN column, verified independently from the raw file.
    assert run.particle_count == 4252


def test_p3_sums_to_100(run):
    assert run.psd["p3"].sum() == pytest.approx(100.0, abs=0.1)
