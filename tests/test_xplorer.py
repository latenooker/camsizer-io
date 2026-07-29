"""Tests for the experimental X-Plorer decoder.

The real ``.xConAlp`` is 60+ MB and is not committed (see ``.gitignore``), so
the deterministic tests build a small synthetic pair that mimics the observed
layout: ``[2-byte flag][16 float32 descriptors][alpha uint8 raster]`` per record.
An opt-in test validates the descriptor decode against the real fixture pair.
"""

from __future__ import annotations

import struct
import warnings
from pathlib import Path

import numpy as np
import pytest

from camsizer_io import DESCRIPTOR_COLUMNS, read_xplorer, validate_structure

FIXTURE_STEM = Path(__file__).parent / "fixtures" / "OK_sand_2_005"

# _DESCRIPTOR_BYTES from the module layout (16 float32).
_DESC_BYTES = 16 * 4


def _write_synthetic_pair(stem, records, preamble=b"measure0\x00syn.xConAlp\x00"):
    """Write a synthetic .xIdx/.xConAlp pair in the observed record layout.

    Args:
        stem: Path stem; ``.xIdx``/``.xConAlp`` are written alongside it.
        records: List of ``(flag_bytes, descriptors(16,), alpha(uint8))`` tuples.
        preamble: Bytes placed before the first record in the container.
    """
    con = bytearray(preamble)
    offsets = []
    for flag, desc, alpha in records:
        offsets.append(len(con))
        con += flag
        con += np.asarray(desc, dtype="<f4").tobytes()
        con += np.asarray(alpha, dtype=np.uint8).tobytes()
    stem.with_suffix(".xConAlp").write_bytes(bytes(con))

    idx = bytearray()
    for i, off in enumerate(offsets):
        idx += struct.pack("<IIII", 0, i * 65536, off, 0)
    stem.with_suffix(".xIdx").write_bytes(bytes(idx))


@pytest.fixture
def synthetic(tmp_path):
    stem = tmp_path / "syn"
    records = [
        (b"\x01\x00", np.arange(16) * 0.01, np.array([0, 100, 200, 0], np.uint8)),
        (b"\x02\x00", np.arange(16) * 0.02, np.array([5, 6, 7, 8, 9, 10], np.uint8)),
        (b"\x03\x00", np.full(16, 0.3), np.array([255, 0], np.uint8)),
    ]
    _write_synthetic_pair(stem, records)
    return stem, records


def test_emits_experimental_warning(synthetic):
    stem, _ = synthetic
    with pytest.warns(UserWarning, match="REVERSE-ENGINEERED"):
        read_xplorer(stem)


def test_record_count_and_offsets(synthetic):
    stem, recs = synthetic
    run = read_xplorer(stem, warn=False)
    assert run.n_records == len(recs)
    assert run.offsets[0] > 0  # preamble precedes the first record


def test_record_splits_descriptors_and_alpha(synthetic):
    stem, recs = synthetic
    run = read_xplorer(stem, warn=False)
    for i, (flag, desc, alpha) in enumerate(recs):
        rec = run.record(i)
        assert rec.flag == flag
        assert rec.descriptors.shape == (16,)
        np.testing.assert_allclose(rec.descriptors, desc, rtol=1e-6)
        np.testing.assert_array_equal(rec.alpha, alpha)


def test_descriptor_matrix_matches_records(synthetic):
    stem, recs = synthetic
    run = read_xplorer(stem, warn=False)
    mat = run.descriptor_matrix()
    assert mat.shape == (len(recs), 16)
    for i, (_, desc, _) in enumerate(recs):
        np.testing.assert_allclose(mat[i], desc, rtol=1e-6)


def test_to_dataframe_columns(synthetic):
    stem, _ = synthetic
    df = read_xplorer(stem, warn=False).to_dataframe()
    assert list(df.columns) == list(DESCRIPTOR_COLUMNS)
    assert len(df) == 3
    assert df.index.name == "record"


def test_resolve_from_any_member(synthetic):
    stem, _ = synthetic
    for path in (stem, stem.with_suffix(".xIdx"), stem.with_suffix(".xConAlp")):
        assert read_xplorer(path, warn=False).n_records == 3


def test_validate_structure_passes(synthetic):
    stem, _ = synthetic
    report = validate_structure(read_xplorer(stem, warn=False))
    assert report.ok and report.offsets_monotonic and report.offsets_in_bounds
    assert report.notes == []


def test_missing_container_raises(tmp_path):
    stem = tmp_path / "lonely"
    stem.with_suffix(".xIdx").write_bytes(struct.pack("<IIII", 0, 0, 8, 0))
    with pytest.raises(FileNotFoundError):
        read_xplorer(stem, warn=False)


# --- opt-in tests against the real 60+ MB container (git-ignored) -------------

_HAVE_REAL = FIXTURE_STEM.with_suffix(".xConAlp").exists()
_skip_real = pytest.mark.skipif(not _HAVE_REAL, reason="real .xConAlp not present")


@_skip_real
def test_real_structural_consistency():
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        run = read_xplorer(FIXTURE_STEM, warn=False)
    assert validate_structure(run).ok
    assert run.n_records == 63286


@_skip_real
def test_real_descriptors_bounded_and_finite():
    """Every record's descriptors are finite and in-family range (alignment)."""
    run = read_xplorer(FIXTURE_STEM, warn=False)
    mat = run.descriptor_matrix()
    assert mat.shape == (63286, 16)
    assert np.isfinite(mat).all()
    # size family (cols 0-8) in mm, shape family (cols 10-15) dimensionless.
    assert (mat[:, :9] >= 0).all() and (mat[:, :9] <= 2).all()
    assert (mat[:, 10:16] >= 0).all() and (mat[:, 10:16] <= 2).all()


@_skip_real
def test_real_size_column_reproduces_reported_x50():
    """Volume-weighted x50 of the xc_min-family column matches the CSV (0.3099)."""
    from camsizer_io import read_csv

    run = read_xplorer(FIXTURE_STEM, warn=False)
    x = np.sort(run.descriptor_matrix()[:, 2])  # size_2 ~ xc_min
    w = x**3
    cw = np.cumsum(w) / w.sum()
    x50 = float(np.interp(0.5, cw, x))
    reported = read_csv(FIXTURE_STEM.with_suffix(".csv")).summary["x50"]
    assert x50 == pytest.approx(reported, rel=0.05)
