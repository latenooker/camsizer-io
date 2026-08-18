"""Tests for the tabular output writer."""

from __future__ import annotations

import importlib.util

import pandas as pd
import pytest

from camsizer_io import write_table

_HAS_PYARROW = importlib.util.find_spec("pyarrow") is not None


@pytest.fixture
def frame() -> pd.DataFrame:
    return pd.DataFrame({"a": [1, 2, 3], "b": [0.1, 0.2, 0.3]})


def test_write_csv_round_trips(tmp_path, frame):
    out = write_table(frame, tmp_path / "t", "csv")
    assert out == tmp_path / "t.csv"
    assert out.exists()
    pd.testing.assert_frame_equal(pd.read_csv(out), frame)


def test_csv_extension_not_doubled(tmp_path, frame):
    out = write_table(frame, tmp_path / "t.csv", "csv")
    assert out == tmp_path / "t.csv"
    assert not (tmp_path / "t.csv.csv").exists()


def test_unknown_format_raises(tmp_path, frame):
    with pytest.raises(ValueError, match="Unsupported table format"):
        write_table(frame, tmp_path / "t", "xlsx")


@pytest.mark.skipif(not _HAS_PYARROW, reason="pyarrow not installed")
def test_write_parquet_round_trips(tmp_path, frame):
    out = write_table(frame, tmp_path / "t", "parquet")
    assert out == tmp_path / "t.parquet"
    pd.testing.assert_frame_equal(pd.read_parquet(out), frame)


@pytest.mark.skipif(_HAS_PYARROW, reason="pyarrow is installed")
def test_parquet_without_pyarrow_raises_clearly(tmp_path, frame):
    with pytest.raises(ImportError, match="pyarrow"):
        write_table(frame, tmp_path / "t", "parquet")
