"""Tests for the argparse command-line interface."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from camsizer_io import cli

FIXTURES = Path(__file__).parent / "fixtures"
CSV = FIXTURES / "OK_sand_2_005.csv"
XLE = FIXTURES / "P_01_cs_xc_min_20260804_180031_003.xle"


def test_read_prints_summary(capsys):
    assert cli.main(["read", str(CSV)]) == 0
    out = capsys.readouterr().out
    assert "x50" in out
    assert "particles" in out


def test_read_stats_adds_folk_ward(capsys):
    assert cli.main(["read", str(CSV), "--stats"]) == 0
    out = capsys.readouterr().out
    assert "sorting_phi" in out


def test_read_writes_psd_table(tmp_path, capsys):
    dest = tmp_path / "psd"
    assert cli.main(["read", str(CSV), "-o", str(dest)]) == 0
    written = tmp_path / "psd.csv"
    assert written.exists()
    df = pd.read_csv(written)
    assert {"bin_lower", "bin_upper", "Q3", "PDN"} <= set(df.columns)


def test_run_writes_long_table(tmp_path):
    dest = tmp_path / "long"
    assert cli.main(["run", str(XLE), "-o", str(dest)]) == 0
    df = pd.read_csv(tmp_path / "long.csv")
    assert "size_def" in df.columns
    assert df["size_def"].nunique() >= 1


def test_batch_writes_long_table(tmp_path):
    dest = tmp_path / "batch"
    assert cli.main(["batch", str(FIXTURES), "-o", str(dest)]) == 0
    df = pd.read_csv(tmp_path / "batch.csv")
    assert "sample" in df.columns and "size_def" in df.columns


def test_no_command_returns_nonzero(capsys):
    assert cli.main([]) == 2
