"""Tests for the experimental X-Plorer structural decoder.

The real ``.xConAlp`` is 60+ MB and is not committed (see ``.gitignore``), so
the deterministic tests build a small synthetic pair that mimics the observed
layout. An opt-in test runs against the real fixture pair when present.
"""

from __future__ import annotations

import struct
import warnings
from pathlib import Path

import numpy as np
import pytest

from camsizer_io import read_xplorer, validate_structure

FIXTURE_STEM = Path(__file__).parent / "fixtures" / "OK_sand_2_005"


def _write_synthetic_pair(stem: Path, blocks: list[np.ndarray], preamble: bytes) -> None:
    """Write a synthetic .xIdx/.xConAlp pair mimicking the observed layout.

    Args:
        stem: Path stem; ``.xIdx`` and ``.xConAlp`` are written alongside it.
        blocks: One float32 array per record (the payload after the 2-byte flag).
        preamble: Bytes to place before the first record in the container.
    """
    con = bytearray(preamble)
    offsets: list[int] = []
    for arr in blocks:
        offsets.append(len(con))
        con += b"\x01\x00"  # 2-byte flag
        con += arr.astype("<f4").tobytes()

    stem.with_suffix(".xConAlp").write_bytes(bytes(con))

    idx = bytearray()
    for i, off in enumerate(offsets):
        # 16-byte record: field0=0, field1=i*65536, field2=offset, field3=0
        idx += struct.pack("<IIII", 0, i * 65536, off, 0)
    stem.with_suffix(".xIdx").write_bytes(bytes(idx))


@pytest.fixture
def synthetic(tmp_path):
    stem = tmp_path / "syn"
    blocks = [
        np.array([0.11, 0.12, 0.13], dtype="<f4"),
        np.array([0.21, 0.22, 0.23, 0.24, 0.25], dtype="<f4"),
        np.array([0.31, 0.32], dtype="<f4"),
    ]
    _write_synthetic_pair(stem, blocks, preamble=b"measure0\x00OK_syn.xConAlp\x00")
    return stem, blocks


def test_emits_experimental_warning(synthetic):
    stem, _ = synthetic
    with pytest.warns(UserWarning, match="REVERSE-ENGINEERED"):
        read_xplorer(stem)


def test_record_count_and_offsets(synthetic):
    stem, blocks = synthetic
    run = read_xplorer(stem, warn=False)
    assert run.n_records == len(blocks)
    assert run.offsets[0] > 0  # preamble precedes the first record


def test_records_roundtrip_payload(synthetic):
    stem, blocks = synthetic
    run = read_xplorer(stem, warn=False)
    for i, expected in enumerate(blocks):
        rec = run.record(i)
        assert rec.flag == b"\x01\x00"
        np.testing.assert_allclose(rec.floats, expected, rtol=1e-6)


def test_preamble_meta_recovered(synthetic):
    stem, _ = synthetic
    run = read_xplorer(stem, warn=False)
    assert any("measure0" in s for s in run.preamble_meta)


def test_resolve_from_any_member(synthetic):
    stem, _ = synthetic
    for path in (stem, stem.with_suffix(".xIdx"), stem.with_suffix(".xConAlp")):
        assert read_xplorer(path, warn=False).n_records == 3


def test_validate_structure_passes(synthetic):
    stem, _ = synthetic
    report = validate_structure(read_xplorer(stem, warn=False))
    assert report.ok
    assert report.offsets_monotonic
    assert report.offsets_in_bounds
    assert report.notes == []


def test_missing_container_raises(tmp_path):
    stem = tmp_path / "lonely"
    stem.with_suffix(".xIdx").write_bytes(struct.pack("<IIII", 0, 0, 8, 0))
    with pytest.raises(FileNotFoundError):
        read_xplorer(stem, warn=False)


@pytest.mark.skipif(
    not FIXTURE_STEM.with_suffix(".xConAlp").exists(),
    reason="real .xConAlp not present (gitignored 60+ MB blob)",
)
def test_real_run_structural_consistency():
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        run = read_xplorer(FIXTURE_STEM, warn=False)
    report = validate_structure(run)
    assert report.ok
    assert run.n_records == 63286  # observed raw detection-record count
    # First and last records materialize without error.
    assert run.record(0).floats.size > 0
    assert run.record(run.n_records - 1).floats.size > 0
