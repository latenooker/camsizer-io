"""Data structures returned by :mod:`camsizer_io` readers."""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd


@dataclass
class RunMeta:
    """Metadata parsed from a CAMSIZER CSV export header.

    Attributes:
        source_file: Raw-data file name referenced in the export header
            (e.g. ``OK_sand_2_005.rdf``).
        method_file: Method/config file name (e.g. ``measure0.afg``).
        size_model: Size-model description string
            (e.g. ``xc_min with shape parameter 1.0000``).
        date: Measurement date as written in the export (``YYYY/MM/DD``).
        time: Measurement time as written in the export (``HH:MM``).
        duration: Measurement duration string (e.g. ``0 min 19 s``).
    """

    source_file: str | None = None
    method_file: str | None = None
    size_model: str | None = None
    date: str | None = None
    time: str | None = None
    duration: str | None = None


@dataclass
class CamsizerRun:
    """A single CAMSIZER measurement parsed from its CSV export.

    Attributes:
        meta: Header metadata (:class:`RunMeta`).
        psd: Per-size-class table with columns ``bin_lower``, ``bin_upper``
            (mm), ``p3`` and ``Q3`` (%, volume/area-weighted density and
            cumulative), the shape means per class ``SPHT3``, ``Symm3``,
            ``b_l3``, and ``PDN`` (particle count in the class).
        summary: Scalar summary values keyed by their export label
            (e.g. ``x10``, ``x50``, ``x90``, ``SPAN3``, ``U3``,
            ``mean_SPHT3``, ``mean_Symm3``, ``mean_b_l3``).
        source_path: Path of the CSV file this run was read from.
    """

    meta: RunMeta = field(default_factory=RunMeta)
    psd: pd.DataFrame = field(default_factory=pd.DataFrame)
    summary: dict[str, float] = field(default_factory=dict)
    source_path: str | None = None

    @property
    def particle_count(self) -> int:
        """Total particle count across all size classes (sum of ``PDN``)."""
        if "PDN" not in self.psd:
            return 0
        return int(self.psd["PDN"].sum())


@dataclass
class ParticleRecord:
    """One raw per-particle record sliced from an X-Plorer ``.xConAlp`` blob.

    This is a *structural* decode only: the byte range is located via the
    ``.xIdx`` offset table and the leading float32 stream is exposed as-is.
    The split between contour vertices and the alpha (grayscale) raster, and
    any physical calibration, are **not** resolved — see the module docstring
    of :mod:`camsizer_io.xplorer`.

    Attributes:
        index: Zero-based record index within the run.
        byte_offset: Start offset of this record inside the ``.xConAlp`` file.
        byte_length: Length of this record in bytes.
        flag: The two-byte record prefix (raw), meaning unconfirmed.
        floats: The record payload reinterpreted as little-endian float32
            (after the 2-byte flag). Contains contour + alpha data, unseparated.
    """

    index: int
    byte_offset: int
    byte_length: int
    flag: bytes
    floats: "object"  # numpy.ndarray[float32]; typed loosely to avoid a hard import here
