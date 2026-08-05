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


SIZE_DEF_ORDER: tuple[str, ...] = ("xc_min", "x_area", "xFe_max", "xFe_min", "xMa_min")

_LONG_COLUMNS = ["sample", "timestamp", "seq", "size_def", "bin_lower",
                 "bin_upper", "p3", "Q3", "SPHT3", "Symm3", "b_l3", "PDN"]


@dataclass
class MeasurementRun:
    """One CAMSIZER measurement across its active size definitions.

    A measurement run writes one export file per size definition (``xc_min``,
    ``x_area`` ...), all sharing a filename ``<date>_<time>_<seq>`` suffix. This
    container groups the parsed :class:`CamsizerRun`s by their canonical
    size-definition key.

    Attributes:
        sample: Sample identity prefix (e.g. ``P_01_cs``).
        timestamp: Shared ``<date>_<time>`` stamp (e.g. ``20260804_180031``).
        seq: Shared sequence field (e.g. ``003``).
        runs: Canonical size-definition key -> parsed :class:`CamsizerRun`.
        source_dir: Directory the files were read from, if known.
    """

    sample: str
    timestamp: str
    seq: str
    runs: dict[str, CamsizerRun] = field(default_factory=dict)
    source_dir: str | None = None

    @property
    def size_defs(self) -> list[str]:
        """Canonical size-definition keys present, in canonical order."""
        known = [k for k in SIZE_DEF_ORDER if k in self.runs]
        extra = [k for k in self.runs if k not in SIZE_DEF_ORDER]
        return known + extra

    @property
    def by_size_def(self) -> dict[str, CamsizerRun]:
        """The size-definition -> run mapping (alias of ``runs``)."""
        return self.runs

    @property
    def primary(self) -> CamsizerRun:
        """The ``xc_min`` run if present, else the first available definition.

        Raises:
            ValueError: If the run contains no size definitions.
        """
        if not self.runs:
            raise ValueError("MeasurementRun has no size definitions.")
        key = "xc_min" if "xc_min" in self.runs else self.size_defs[0]
        return self.runs[key]

    def __getitem__(self, key: str) -> CamsizerRun:
        """Return the :class:`CamsizerRun` for canonical size-definition ``key``."""
        return self.runs[key]

    def to_long(self) -> pd.DataFrame:
        """Return this run's size classes across its size definitions (tidy).

        Returns:
            A long-format DataFrame with columns
            ``sample, timestamp, seq, size_def`` followed by the per-class PSD
            columns. Size definitions appear in canonical order; empty runs
            yield no rows.
        """
        frames = []
        for size_def in self.size_defs:
            psd = self.runs[size_def].psd.copy()
            psd.insert(0, "size_def", size_def)
            psd.insert(0, "seq", self.seq)
            psd.insert(0, "timestamp", self.timestamp)
            psd.insert(0, "sample", self.sample)
            frames.append(psd)
        if not frames:
            return pd.DataFrame(columns=_LONG_COLUMNS)
        return pd.concat(frames, ignore_index=True)[_LONG_COLUMNS]
