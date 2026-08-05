"""Tests for grouping five per-size-definition exports into a MeasurementRun."""

from __future__ import annotations

import pytest

from camsizer_io.run_reader import (
    _canonical_size_def,
    _parse_run_filename,
)


@pytest.mark.parametrize(
    "name, expected",
    [
        ("P_01_cs_x_area_20260804_180031_003.xle",
         ("P_01_cs", "x_area", "20260804", "180031", "003")),
        ("P_01_cs_xc_min_20260804_180031_003.xle",
         ("P_01_cs", "xc_min", "20260804", "180031", "003")),
        ("P_01_cs_xFemax_20260804_180031_003.xle",
         ("P_01_cs", "xFemax", "20260804", "180031", "003")),
        ("P_17_cs_xMamin_20260804_173208_002.xld",
         ("P_17_cs", "xMamin", "20260804", "173208", "002")),
    ],
)
def test_parse_run_filename(name, expected):
    assert _parse_run_filename(name) == expected


def test_parse_run_filename_rejects_nonconforming():
    with pytest.raises(ValueError):
        _parse_run_filename("not_a_camsizer_file.txt")


@pytest.mark.parametrize(
    "size_model, expected",
    [
        ("xc_min with shape parameter 1.0000", "xc_min"),
        ("x_area with shape parameter 1.0000", "x_area"),
        ("xFe_max with shape parameter 1.0000", "xFe_max"),
    ],
)
def test_canonical_size_def(size_model, expected):
    assert _canonical_size_def(size_model) == expected


def test_canonical_size_def_rejects_empty():
    with pytest.raises(ValueError):
        _canonical_size_def(None)
