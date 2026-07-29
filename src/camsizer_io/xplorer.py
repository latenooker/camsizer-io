"""EXPERIMENTAL, reverse-engineered reader for X-Plorer particle binaries.

.. warning::

   This module decodes the CAMSIZER X2 Particle X-Plorer ``.xIdx`` / ``.xConAlp``
   files by **reverse engineering**. Microtrac publishes no specification for
   these formats. The decode here is *structural only* and **unvalidated**
   against the instrument software. Do **not** use it for publication-grade
   morphometry — export particle images from Particle X-Plorer for that
   (see the project README and SOP §10.2).

What is (empirically) understood, from the ``OK_sand_2_005`` run:

* ``.xIdx`` is a flat table of 16-byte records, four little-endian ``uint32``
  fields each. Field 2 is a **byte offset** into ``.xConAlp`` and is strictly
  increasing across the whole table; field 1 is a record counter
  (``index * 65536``); fields 0 and 3 are not confirmed.
* ``.xConAlp`` begins with a preamble (bytes ``0 .. offsets[0]``) holding ASCII
  metadata, then one variable-length record per index entry, laid out as
  ``[2-byte flag][16 float32 descriptors][alpha raster]``.

The 16-float descriptor header is **validated** against the CSV export: across
all 63286 records the columns are finite and bounded (size family in mm, shape
family dimensionless in ``[0, ~1.4]``), and the volume-weighted median of the
``xc_min``-family column reproduces the reported ``x50`` (0.311 vs 0.3099 mm).
The exact CAMSIZER name of each individual column is *inferred*, not confirmed
against the software — see :data:`DESCRIPTOR_COLUMNS`.

What is NOT resolved: the width/height of the trailing alpha raster (2-D
structure is confirmed by row autocorrelation, but no dimension field is
identified, so ``alpha`` is returned raw/1-D); the exact descriptor↔name
mapping; whether a record equals one PSD particle (the record count is the raw
detection set and does **not** equal the CSV ``PDN`` total); and whether the
layout is stable across CAMSIZER software versions.
"""

from __future__ import annotations

import re
import warnings
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from .models import ParticleRecord

_IDX_RECORD_BYTES = 16
_OFFSET_FIELD = 2  # zero-based uint32 field in each .xIdx record holding the byte offset
_FLAG_BYTES = 2  # per-record prefix in .xConAlp before the descriptor header
_N_DESCRIPTORS = 16  # float32 values in the per-record descriptor header
_DESCRIPTOR_BYTES = _N_DESCRIPTORS * 4  # = 64

#: Provisional column names for the 16-value per-particle descriptor header.
#:
#: The **family** of each column is validated (``size_*`` are diameters in mm;
#: ``shape_*`` are dimensionless in ``[0, ~1.4]``; ``aux_9`` is an area-like
#: value with a larger dynamic range). Empirically, ``size_2`` behaves as the
#: CAMSIZER ``xc_min`` model (its volume-weighted x50 reproduces the reported
#: value), the three size triples order as widths < ``xc_min`` < Feret-max, and
#: ``shape_5`` (which can exceed 1) behaves as symmetry. The exact CAMSIZER name
#: of each column is **not** confirmed against the software — treat the specific
#: labels as a starting point, not ground truth.
DESCRIPTOR_COLUMNS: tuple[str, ...] = (
    "size_0", "size_1", "size_2", "size_3", "size_4", "size_5",
    "size_6", "size_7", "size_8", "aux_9",
    "shape_0", "shape_1", "shape_2", "shape_3", "shape_4", "shape_5",
)

_EXPERIMENTAL_WARNING = (
    "camsizer_io.xplorer is a REVERSE-ENGINEERED, UNVALIDATED decoder for the "
    "proprietary CAMSIZER X-Plorer .xIdx/.xConAlp format. It performs a "
    "structural decode only (no contour/alpha separation, no calibration) and "
    "must not be used for publication-grade morphometry. Export particle "
    "images from Particle X-Plorer instead."
)


@dataclass
class StructureReport:
    """Result of validating the structural self-consistency of a run.

    Attributes:
        ok: True if every structural check passed.
        n_records: Number of index records found.
        offsets_monotonic: Whether ``.xIdx`` offsets strictly increase.
        offsets_in_bounds: Whether all offsets lie within the ``.xConAlp`` file.
        con_file_bytes: Size of the ``.xConAlp`` file in bytes.
        notes: Human-readable notes about any check that failed.
    """

    ok: bool
    n_records: int
    offsets_monotonic: bool
    offsets_in_bounds: bool
    con_file_bytes: int
    notes: list[str] = field(default_factory=list)


@dataclass
class XplorerRun:
    """A structurally-decoded X-Plorer run (EXPERIMENTAL — see module docs).

    Attributes:
        path_idx: Path to the ``.xIdx`` index file.
        path_con: Path to the ``.xConAlp`` container file.
        offsets: Byte offset of each record's start within ``.xConAlp``.
        lengths: Byte length of each record.
        n_records: Number of records (``len(offsets)``).
        preamble_meta: ASCII strings recovered from the container preamble.
        con_file_bytes: Size of the ``.xConAlp`` file in bytes.
    """

    path_idx: Path
    path_con: Path
    offsets: np.ndarray
    lengths: np.ndarray
    preamble_meta: list[str]
    con_file_bytes: int

    @property
    def n_records(self) -> int:
        """Number of decoded records."""
        return int(len(self.offsets))

    def record(self, i: int) -> ParticleRecord:
        """Materialize a single record: flag, 16 descriptors, and alpha raster.

        Args:
            i: Zero-based record index.

        Returns:
            A :class:`~camsizer_io.models.ParticleRecord` with the validated
            16-value descriptor header and the raw (1-D) alpha silhouette bytes.

        Raises:
            IndexError: If ``i`` is out of range.
        """
        if not 0 <= i < self.n_records:
            raise IndexError(f"record index {i} out of range [0, {self.n_records})")
        start = int(self.offsets[i])
        length = int(self.lengths[i])
        with open(self.path_con, "rb") as fh:
            fh.seek(start)
            blob = fh.read(length)
        flag = blob[:_FLAG_BYTES]
        desc_bytes = blob[_FLAG_BYTES : _FLAG_BYTES + _DESCRIPTOR_BYTES]
        descriptors = np.frombuffer(desc_bytes, dtype="<f4").copy()
        alpha = np.frombuffer(blob[_FLAG_BYTES + _DESCRIPTOR_BYTES :], dtype=np.uint8).copy()
        return ParticleRecord(
            index=i,
            byte_offset=start,
            byte_length=length,
            flag=flag,
            descriptors=descriptors,
            alpha=alpha,
        )

    def descriptor_matrix(self) -> np.ndarray:
        """Extract the per-particle descriptor header for every record.

        This reads only the 16-float header of each record (not the alpha
        rasters), so it is fast and memory-light even for large runs.

        Returns:
            A ``(n_records, 16)`` float32 array. Column order follows
            :data:`DESCRIPTOR_COLUMNS`.
        """
        raw = np.fromfile(self.path_con, dtype=np.uint8)
        starts = self.offsets + _FLAG_BYTES
        gather = starts[:, None] + np.arange(_DESCRIPTOR_BYTES)[None, :]
        return raw[gather].view("<f4").reshape(self.n_records, _N_DESCRIPTORS)

    def to_dataframe(self):
        """Return the per-particle descriptor table as a pandas DataFrame.

        Returns:
            A DataFrame of shape ``(n_records, 16)`` with columns
            :data:`DESCRIPTOR_COLUMNS`, indexed by record number.

        Note:
            The ``size_*`` columns are diameters in millimetres and the
            ``shape_*`` columns are dimensionless; exact CAMSIZER descriptor
            names per column are inferred, not confirmed (see module docs).
        """
        import pandas as pd

        df = pd.DataFrame(self.descriptor_matrix(), columns=list(DESCRIPTOR_COLUMNS))
        df.index.name = "record"
        return df

    def iter_records(self, limit: int | None = None):
        """Iterate records lazily.

        Args:
            limit: Maximum number of records to yield (``None`` = all).

        Yields:
            :class:`~camsizer_io.models.ParticleRecord` in index order.
        """
        n = self.n_records if limit is None else min(limit, self.n_records)
        for i in range(n):
            yield self.record(i)


def _resolve_pair(path: str | Path) -> tuple[Path, Path]:
    """Resolve the ``.xIdx`` / ``.xConAlp`` pair from any member path or stem.

    Args:
        path: Path to the ``.xIdx``, the ``.xConAlp``, or the shared stem.

    Returns:
        ``(idx_path, con_path)``.

    Raises:
        FileNotFoundError: If either member of the pair is missing.
    """
    p = Path(path)
    base = p.with_suffix("") if p.suffix in {".xIdx", ".xConAlp"} else p
    idx_path = base.with_suffix(".xIdx")
    con_path = base.with_suffix(".xConAlp")
    if not idx_path.exists():
        raise FileNotFoundError(f"Index file not found: {idx_path}")
    if not con_path.exists():
        raise FileNotFoundError(f"Container file not found: {con_path}")
    return idx_path, con_path


def _read_offsets(idx_path: Path) -> np.ndarray:
    """Read the byte-offset column from an ``.xIdx`` file.

    Args:
        idx_path: Path to the ``.xIdx`` file.

    Returns:
        Int64 array of per-record byte offsets into ``.xConAlp``.
    """
    raw = np.frombuffer(idx_path.read_bytes(), dtype="<u4")
    usable = (len(raw) // (_IDX_RECORD_BYTES // 4)) * (_IDX_RECORD_BYTES // 4)
    table = raw[:usable].reshape(-1, _IDX_RECORD_BYTES // 4)
    return table[:, _OFFSET_FIELD].astype(np.int64)


def _read_preamble_meta(con_path: Path, first_offset: int) -> list[str]:
    """Recover printable ASCII strings from the container preamble.

    Args:
        con_path: Path to the ``.xConAlp`` file.
        first_offset: Byte offset of the first record (end of the preamble).

    Returns:
        List of ASCII strings (length >= 4) found before the first record.
    """
    with open(con_path, "rb") as fh:
        pre = fh.read(max(0, first_offset))
    return [m.decode("ascii", "replace") for m in re.findall(rb"[ -~]{4,}", pre)]


def read_xplorer(path: str | Path, *, warn: bool = True) -> XplorerRun:
    """Structurally decode an X-Plorer ``.xIdx`` / ``.xConAlp`` pair.

    .. warning::
       EXPERIMENTAL and unvalidated — see the module docstring. Emits a
       :class:`UserWarning` on every call unless ``warn=False``.

    Args:
        path: Path to the ``.xIdx``, the ``.xConAlp``, or the shared stem.
        warn: If True (default), emit the experimental-use warning.

    Returns:
        An :class:`XplorerRun` exposing per-record byte ranges and lazy
        float32 payload access.

    Raises:
        FileNotFoundError: If either file of the pair is missing.
        ValueError: If the index table contains no records.
    """
    if warn:
        warnings.warn(_EXPERIMENTAL_WARNING, UserWarning, stacklevel=2)

    idx_path, con_path = _resolve_pair(path)
    offsets = _read_offsets(idx_path)
    if len(offsets) == 0:
        raise ValueError(f"No records found in index file: {idx_path}")

    con_bytes = con_path.stat().st_size
    lengths = np.diff(np.append(offsets, con_bytes))
    preamble = _read_preamble_meta(con_path, int(offsets[0]))

    return XplorerRun(
        path_idx=idx_path,
        path_con=con_path,
        offsets=offsets,
        lengths=lengths,
        preamble_meta=preamble,
        con_file_bytes=con_bytes,
    )


def validate_structure(run: XplorerRun) -> StructureReport:
    """Check the structural self-consistency of a decoded run.

    This validates only what can be checked without ground truth: that the
    index offsets strictly increase and fall within the container file. It
    does **not** and cannot validate the semantic content of the records.

    Args:
        run: An :class:`XplorerRun` from :func:`read_xplorer`.

    Returns:
        A :class:`StructureReport`.
    """
    notes: list[str] = []
    offsets = run.offsets

    monotonic = bool(np.all(np.diff(offsets) > 0)) if len(offsets) > 1 else True
    if not monotonic:
        notes.append("Index offsets are not strictly increasing.")

    in_bounds = bool(offsets[0] >= 0 and offsets[-1] < run.con_file_bytes)
    if not in_bounds:
        notes.append(
            f"Offsets [{int(offsets[0])}, {int(offsets[-1])}] fall outside "
            f"container size {run.con_file_bytes}."
        )

    ok = monotonic and in_bounds
    return StructureReport(
        ok=ok,
        n_records=run.n_records,
        offsets_monotonic=monotonic,
        offsets_in_bounds=in_bounds,
        con_file_bytes=run.con_file_bytes,
        notes=notes,
    )
