"""camsizer-io: read Microtrac CAMSIZER X2 dry-mode outputs into tidy Python.

Two paths, deliberately unequal in trust:

* :func:`read_csv` + :func:`folk_ward` — the **reliable** path. Parses the
  documented UTF-16 CSV export and computes standard grain-size statistics.
* :func:`read_xplorer` — an **experimental, reverse-engineered** structural
  decoder for the proprietary ``.xIdx`` / ``.xConAlp`` particle binaries. It is
  unvalidated against the instrument software; for real morphometry, export
  particle images from Particle X-Plorer instead.

The ``.rdf`` and ``.cdf`` raw binaries are intentionally out of scope.
"""

from __future__ import annotations

from .csv_reader import read_csv
from .models import CamsizerRun, ParticleRecord, RunMeta
from .stats import FolkWard, folk_ward, percentile_mm
from .xplorer import StructureReport, XplorerRun, read_xplorer, validate_structure

__version__ = "0.1.0"

__all__ = [
    "read_csv",
    "CamsizerRun",
    "RunMeta",
    "folk_ward",
    "percentile_mm",
    "FolkWard",
    "read_xplorer",
    "validate_structure",
    "XplorerRun",
    "StructureReport",
    "ParticleRecord",
    "__version__",
]
