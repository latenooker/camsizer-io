"""Tests for grouping five per-size-definition exports into a MeasurementRun."""

from __future__ import annotations

from pathlib import Path

import pytest

from camsizer_io import read_batch, read_run, to_long
from camsizer_io.models import SIZE_DEF_ORDER
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


FIX = Path(__file__).parent / "fixtures"
_STAMP = "20260804_180031_003"


def test_read_run_finds_all_five_defs():
    mrun = read_run(FIX / f"P_01_cs_xc_min_{_STAMP}.xle")
    assert set(mrun.size_defs) == set(SIZE_DEF_ORDER)
    assert mrun.sample == "P_01_cs"
    assert mrun.timestamp == "20260804_180031"
    assert mrun.seq == "003"
    assert mrun["x_area"].summary["x50"] == pytest.approx(1.3419, abs=1e-4)
    assert mrun["xMa_min"].summary["x50"] == pytest.approx(1.0063, abs=1e-4)


def test_read_run_from_any_sibling_is_equivalent():
    a = read_run(FIX / f"P_01_cs_xc_min_{_STAMP}.xle")
    b = read_run(FIX / f"P_01_cs_xFemax_{_STAMP}.xle")
    assert a.size_defs == b.size_defs
    assert a.timestamp == b.timestamp


def test_read_run_partial_warns(tmp_path):
    # Only two of the five definitions present -> warn, still return them.
    for tok in ("xc_min", "x_area"):
        src = (FIX / f"P_01_cs_{tok}_{_STAMP}.xle").read_bytes()
        (tmp_path / f"P_01_cs_{tok}_{_STAMP}.xle").write_bytes(src)
    with pytest.warns(UserWarning):
        mrun = read_run(tmp_path / f"P_01_cs_xc_min_{_STAMP}.xle")
    assert set(mrun.size_defs) == {"xc_min", "x_area"}


def test_read_run_token_mismatch_warns(tmp_path):
    # Header says xc_min but the filename token says xFemax -> trust the header.
    src = (FIX / f"P_01_cs_xc_min_{_STAMP}.xle").read_bytes()
    (tmp_path / f"P_01_cs_xFemax_{_STAMP}.xle").write_bytes(src)
    with pytest.warns(UserWarning, match="trusting header"):
        mrun = read_run(tmp_path / f"P_01_cs_xFemax_{_STAMP}.xle")
    assert set(mrun.size_defs) == {"xc_min"}


def test_read_run_duplicate_size_def_warns(tmp_path):
    # Both files' headers say xc_min, so the run group has a duplicate
    # canonical size definition even though their filename tokens differ.
    src = (FIX / f"P_01_cs_xc_min_{_STAMP}.xle").read_bytes()
    (tmp_path / f"P_01_cs_xc_min_{_STAMP}.xle").write_bytes(src)
    (tmp_path / f"P_01_cs_xMamin_{_STAMP}.xle").write_bytes(src)
    with pytest.warns(UserWarning, match="Duplicate size definition"):
        mrun = read_run(tmp_path / f"P_01_cs_xc_min_{_STAMP}.xle")
    assert set(mrun.size_defs) == {"xc_min"}


def test_read_batch_groups_one_run():
    runs = read_batch(FIX, pattern="*.xle")
    assert len(runs) == 1
    assert set(runs[0].size_defs) == set(SIZE_DEF_ORDER)


def test_to_long_accepts_single_and_list():
    runs = read_batch(FIX, pattern="*.xle")
    one = to_long(runs[0])
    many = to_long(runs)
    assert len(one) == 5 * 1002
    assert len(many) == 5 * 1002
    assert list(many.columns)[:4] == ["sample", "timestamp", "seq", "size_def"]
