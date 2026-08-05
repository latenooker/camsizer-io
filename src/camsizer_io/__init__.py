"""camsizer-io: read Microtrac CAMSIZER X2 dry-mode outputs into tidy Python.

Two paths, deliberately unequal in trust:

* :func:`read_csv` + :func:`folk_ward` — the **reliable** path. Parses the
  documented UTF-16 CSV export and computes standard grain-size statistics.
* :func:`read_xplorer` — an **experimental, reverse-engineered** decoder for the
  proprietary ``.xIdx`` / ``.xConAlp`` particle binaries. It yields a per-particle
  size/shape descriptor table (``to_dataframe``) whose *extraction* is validated
  against the CSV export, plus raw alpha silhouette rasters. Per-column
  descriptor names are inferred; for morphometry from the silhouette images,
  export from Particle X-Plorer instead.

The ``.rdf`` and ``.cdf`` raw binaries are intentionally out of scope.
"""

from __future__ import annotations

from .csv_reader import read_csv
from .models import CamsizerRun, MeasurementRun, ParticleRecord, RunMeta
from .run_reader import read_batch, read_run, to_long
from .stats import FolkWard, folk_ward, percentile_mm
from .xplorer import (
    DESCRIPTOR_COLUMNS,
    StructureReport,
    XplorerRun,
    read_xplorer,
    validate_structure,
)

__version__ = "0.1.0"

__all__ = [
    "read_csv",
    "read_run",
    "read_batch",
    "to_long",
    "CamsizerRun",
    "MeasurementRun",
    "RunMeta",
    "folk_ward",
    "percentile_mm",
    "FolkWard",
    "read_xplorer",
    "validate_structure",
    "XplorerRun",
    "StructureReport",
    "DESCRIPTOR_COLUMNS",
    "ParticleRecord",
    "__version__",
]
