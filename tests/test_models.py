"""Tests for the MeasurementRun container."""

from __future__ import annotations

from pathlib import Path

import pytest

from camsizer_io import read_csv
from camsizer_io.models import SIZE_DEF_ORDER, MeasurementRun

FIX = Path(__file__).parent / "fixtures"
_STAMP = "20260804_180031_003"
_TOKENS = {"x_area": "x_area", "xc_min": "xc_min", "xFemax": "xFe_max",
           "xFemin": "xFe_min", "xMamin": "xMa_min"}


@pytest.fixture
def mrun():
    runs = {canon: read_csv(FIX / f"P_01_cs_{tok}_{_STAMP}.xle")
            for tok, canon in _TOKENS.items()}
    return MeasurementRun(sample="P_01_cs", timestamp="20260804_180031",
                          seq="003", runs=runs)


def test_size_defs_in_canonical_order(mrun):
    assert mrun.size_defs == list(SIZE_DEF_ORDER)


def test_getitem_and_primary(mrun):
    assert mrun["xc_min"].summary["x50"] == pytest.approx(1.0993, abs=1e-4)
    assert mrun.primary is mrun["xc_min"]


def test_to_long_shape_and_columns(mrun):
    df = mrun.to_long()
    assert list(df.columns) == ["sample", "timestamp", "seq", "size_def",
                                "bin_lower", "bin_upper", "p3", "Q3",
                                "SPHT3", "Symm3", "b_l3", "PDN"]
    assert len(df) == 5 * 1002
    assert set(df["size_def"]) == set(SIZE_DEF_ORDER)
    assert (df["sample"] == "P_01_cs").all()


def test_primary_falls_back_when_no_xc_min():
    run = read_csv(FIX / f"P_01_cs_x_area_{_STAMP}.xle")
    mr = MeasurementRun(sample="P_01_cs", timestamp="20260804_180031",
                        seq="003", runs={"x_area": run})
    assert mr.primary is run
