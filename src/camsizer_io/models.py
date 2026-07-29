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
    """One per-particle record decoded from an X-Plorer ``.xConAlp`` blob.

    Each record is laid out as ``[2-byte flag][16 float32 descriptors][alpha
    raster]``. The 16-value descriptor header is a **validated** per-particle
    size/shape vector (its column aggregates reproduce the CSV summary; see
    :mod:`camsizer_io.xplorer`). The trailing ``alpha`` bytes are the particle's
    grayscale silhouette; 2-D structure is confirmed but the exact width/height
    field is not, so it is exposed as a raw 1-D array (not reshaped).

    Attributes:
        index: Zero-based record index within the run.
        byte_offset: Start offset of this record inside the ``.xConAlp`` file.
        byte_length: Length of this record in bytes.
        flag: The two-byte record prefix (raw); small integer, meaning unconfirmed.
        descriptors: The 16 per-particle descriptor floats (size + shape).
            See :data:`camsizer_io.xplorer.DESCRIPTOR_COLUMNS`.
        alpha: The trailing grayscale silhouette bytes as a 1-D ``uint8`` array
            (not reshaped to 2-D).
    """

    index: int
    byte_offset: int
    byte_length: int
    flag: bytes
    descriptors: "object"  # numpy.ndarray[float32], shape (16,)
    alpha: "object"  # numpy.ndarray[uint8], 1-D raw raster
