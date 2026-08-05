# Multi-Size-Definition Runs Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Read a CAMSIZER X2 measurement's five per-size-definition export files as one grouped object, with a tidy long-format batch export and Folk & Ward stats that default to the sieve-comparable `xc_min` definition.

**Architecture:** A grouping/aggregation layer over the existing per-file `read_csv`. `CamsizerRun` (one size definition) is unchanged; a new `MeasurementRun` composes up to five of them, keyed by canonical size-definition. A new `run_reader.py` holds filename parsing, `read_run`, `read_batch`, and `to_long`. `folk_ward` gains an `isinstance` dispatch for `MeasurementRun`.

**Tech Stack:** Python ≥ 3.11, numpy, pandas, pytest. `src/` layout, setuptools.

## Global Constraints

- Python ≥ 3.11; dependencies limited to numpy ≥ 1.24, pandas ≥ 2.0 (no new deps).
- Every module starts with `from __future__ import annotations`.
- Modern type hints (`str | None`, `list[str]`); Google-style docstrings with Args/Returns/Raises on every public function and class; private symbols prefixed `_`.
- `CamsizerRun` public behavior and `folk_ward(camsizer_run)` results must stay byte-identical (back-compat).
- Canonical size-definition keys and order: `("xc_min", "x_area", "xFe_max", "xFe_min", "xMa_min")`.
- The canonical size-definition is derived from each file's header `size_model` (authoritative); the filename token is used only for a cross-check warning.
- Commit trailer on every commit: `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`.
- Ground-truth fixture values (run `P_01_cs … 20260804_180031_003`, 1002 classes each): x50 — `x_area` 1.3419, `xc_min` 1.0993, `xFe_max` 1.7783, `xFe_min` 1.1386, `xMa_min` 1.0063 mm. Folk & Ward on `xc_min`: `median_phi` −0.1366, `sorting_phi` 0.6598, `d_mm["d50"]` 1.0993. Header: `method_file="X_Fall_PPX.afg"`, `date="2026/08/04"`.

---

### Task 1: Filename parsing + canonical size-definition helpers

**Files:**
- Create: `src/camsizer_io/run_reader.py`
- Test: `tests/test_run_reader.py`

**Interfaces:**
- Consumes: nothing (leaf module).
- Produces:
  - `SIZE_DEF_ORDER: tuple[str, ...]` — re-exported from `models` (see Task 2); for Task 1 define it locally and move in Task 2. **To avoid rework, import it from `models` — but `models` gains it in Task 2.** Therefore Task 1 defines `SIZE_DEF_ORDER` in `run_reader.py` temporarily and Task 2 introduces the canonical copy in `models`; Task 3 switches `run_reader` to import from `models`. (Simpler: define `SIZE_DEF_ORDER` in `models` first — but Task 1 is leaf. Keep the local definition here and re-point in Task 3.)
  - `_parse_run_filename(name: str) -> tuple[str, str, str, str, str]` returning `(sample, size_token, date, time, seq)`. Raises `ValueError` if `name` does not match the run pattern.
  - `_TOKEN_TO_CANONICAL: dict[str, str]` mapping filename tokens to canonical keys.
  - `_canonical_size_def(size_model: str | None) -> str` — first word of the header `size_model` (e.g. `"xc_min with shape parameter 1.0000"` → `"xc_min"`). Raises `ValueError` if `size_model` is falsy.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_run_reader.py
"""Tests for grouping five per-size-definition exports into a MeasurementRun."""

from __future__ import annotations

import pytest

from camsizer_io.run_reader import (
    _canonical_size_def,
    _parse_run_filename,
)


@pytest.mark.parametrize(
    "name, expected",
    [
        ("P_01_cs_x_area_20260804_180031_003.xle",
         ("P_01_cs", "x_area", "20260804", "180031", "003")),
        ("P_01_cs_xc_min_20260804_180031_003.xle",
         ("P_01_cs", "xc_min", "20260804", "180031", "003")),
        ("P_01_cs_xFemax_20260804_180031_003.xle",
         ("P_01_cs", "xFemax", "20260804", "180031", "003")),
        ("P_17_cs_xMamin_20260804_173208_002.xld",
         ("P_17_cs", "xMamin", "20260804", "173208", "002")),
    ],
)
def test_parse_run_filename(name, expected):
    assert _parse_run_filename(name) == expected


def test_parse_run_filename_rejects_nonconforming():
    with pytest.raises(ValueError):
        _parse_run_filename("not_a_camsizer_file.txt")


@pytest.mark.parametrize(
    "size_model, expected",
    [
        ("xc_min with shape parameter 1.0000", "xc_min"),
        ("x_area with shape parameter 1.0000", "x_area"),
        ("xFe_max with shape parameter 1.0000", "xFe_max"),
    ],
)
def test_canonical_size_def(size_model, expected):
    assert _canonical_size_def(size_model) == expected


def test_canonical_size_def_rejects_empty():
    with pytest.raises(ValueError):
        _canonical_size_def(None)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd camsizer-io && pytest tests/test_run_reader.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'camsizer_io.run_reader'`.

- [ ] **Step 3: Write minimal implementation**

```python
# src/camsizer_io/run_reader.py
"""Group per-size-definition CAMSIZER exports into whole measurements.

A CAMSIZER X2 measurement with several size definitions active writes one
export file per definition, all sharing the same ``<date>_<time>_<seq>``
filename suffix. This module discovers those siblings, parses each with
:func:`camsizer_io.read_csv`, and assembles them into a
:class:`~camsizer_io.models.MeasurementRun`.
"""

from __future__ import annotations

import re

# Canonical size-definition keys, in physical/reporting order. (Task 3 will
# switch this to a re-import from camsizer_io.models.)
SIZE_DEF_ORDER: tuple[str, ...] = ("xc_min", "x_area", "xFe_max", "xFe_min", "xMa_min")

# Filename token (as written by the software) -> canonical key, for cross-check.
_TOKEN_TO_CANONICAL: dict[str, str] = {
    "xc_min": "xc_min",
    "x_area": "x_area",
    "xFemax": "xFe_max",
    "xFemin": "xFe_min",
    "xMamin": "xMa_min",
}

# <sample ending in _cs>_<token>_<8-digit date>_<6-digit time>_<seq>.<ext>
_RUN_FILENAME_RE = re.compile(
    r"^(?P<sample>.+?_cs)_(?P<token>.+?)_(?P<date>\d{8})_(?P<time>\d{6})_(?P<seq>\d+)$"
)


def _parse_run_filename(name: str) -> tuple[str, str, str, str, str]:
    """Split a CAMSIZER export filename into its run-identity fields.

    Args:
        name: File name (with or without extension), e.g.
            ``P_01_cs_x_area_20260804_180031_003.xle``.

    Returns:
        ``(sample, size_token, date, time, seq)``.

    Raises:
        ValueError: If ``name`` does not match the run filename pattern.
    """
    stem = name.rsplit(".", 1)[0]
    m = _RUN_FILENAME_RE.match(stem)
    if m is None:
        raise ValueError(f"Not a CAMSIZER run filename: {name!r}")
    return (
        m.group("sample"),
        m.group("token"),
        m.group("date"),
        m.group("time"),
        m.group("seq"),
    )


def _canonical_size_def(size_model: str | None) -> str:
    """Return the canonical size-definition key from a header ``size_model``.

    Args:
        size_model: Header string, e.g. ``xc_min with shape parameter 1.0000``.

    Returns:
        The leading token, e.g. ``xc_min``.

    Raises:
        ValueError: If ``size_model`` is ``None`` or empty.
    """
    if not size_model:
        raise ValueError("Cannot derive size definition from empty size_model.")
    return size_model.split()[0].strip()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_run_reader.py -v`
Expected: PASS (all parametrized cases).

- [ ] **Step 5: Commit**

```bash
git add src/camsizer_io/run_reader.py tests/test_run_reader.py
git commit -m "feat(run): filename parsing + canonical size-def helpers

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 2: `MeasurementRun` model

**Files:**
- Modify: `src/camsizer_io/models.py` (append `SIZE_DEF_ORDER` and `MeasurementRun`)
- Test: `tests/test_models.py` (create)
- Add (commit binary fixtures): `tests/fixtures/P_01_cs_{x_area,xc_min,xFemax,xFemin,xMamin}_20260804_180031_003.xle` (already copied into the working tree).

**Interfaces:**
- Consumes: `CamsizerRun` (existing), `read_csv` (existing, reads `.xle`).
- Produces:
  - `SIZE_DEF_ORDER: tuple[str, ...]` in `models` (canonical home).
  - `MeasurementRun` dataclass with fields `sample: str`, `timestamp: str`, `seq: str`, `runs: dict[str, CamsizerRun]`, `source_dir: str | None = None`; properties `size_defs -> list[str]`, `by_size_def -> dict[str, CamsizerRun]`, `primary -> CamsizerRun`; methods `__getitem__(key: str) -> CamsizerRun`, `to_long() -> pd.DataFrame`.
  - `to_long()` columns (fixed order): `["sample", "timestamp", "seq", "size_def", "bin_lower", "bin_upper", "p3", "Q3", "SPHT3", "Symm3", "b_l3", "PDN"]`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_models.py
"""Tests for the MeasurementRun container."""

from __future__ import annotations

from pathlib import Path

import pytest

from camsizer_io import read_csv
from camsizer_io.models import SIZE_DEF_ORDER, MeasurementRun

FIX = Path(__file__).parent / "fixtures"
_STAMP = "20260804_180031_003"
_TOKENS = {"x_area": "x_area", "xc_min": "xc_min", "xFemax": "xFe_max",
           "xFemin": "xFe_min", "xMamin": "xMa_min"}


@pytest.fixture
def mrun():
    runs = {canon: read_csv(FIX / f"P_01_cs_{tok}_{_STAMP}.xle")
            for tok, canon in _TOKENS.items()}
    return MeasurementRun(sample="P_01_cs", timestamp="20260804_180031",
                          seq="003", runs=runs)


def test_size_defs_in_canonical_order(mrun):
    assert mrun.size_defs == list(SIZE_DEF_ORDER)


def test_getitem_and_primary(mrun):
    assert mrun["xc_min"].summary["x50"] == pytest.approx(1.0993, abs=1e-4)
    assert mrun.primary is mrun["xc_min"]


def test_to_long_shape_and_columns(mrun):
    df = mrun.to_long()
    assert list(df.columns) == ["sample", "timestamp", "seq", "size_def",
                                "bin_lower", "bin_upper", "p3", "Q3",
                                "SPHT3", "Symm3", "b_l3", "PDN"]
    assert len(df) == 5 * 1002
    assert set(df["size_def"]) == set(SIZE_DEF_ORDER)
    assert (df["sample"] == "P_01_cs").all()


def test_primary_falls_back_when_no_xc_min():
    run = read_csv(FIX / f"P_01_cs_x_area_{_STAMP}.xle")
    mr = MeasurementRun(sample="P_01_cs", timestamp="20260804_180031",
                        seq="003", runs={"x_area": run})
    assert mr.primary is run
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_models.py -v`
Expected: FAIL — `ImportError: cannot import name 'MeasurementRun'` (and `SIZE_DEF_ORDER`).

- [ ] **Step 3: Write minimal implementation**

Append to `src/camsizer_io/models.py` (after the existing `CamsizerRun`):

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_models.py -v`
Expected: PASS.

- [ ] **Step 5: Commit** (includes the binary fixtures)

```bash
git add src/camsizer_io/models.py tests/test_models.py \
        tests/fixtures/P_01_cs_x_area_20260804_180031_003.xle \
        tests/fixtures/P_01_cs_xc_min_20260804_180031_003.xle \
        tests/fixtures/P_01_cs_xFemax_20260804_180031_003.xle \
        tests/fixtures/P_01_cs_xFemin_20260804_180031_003.xle \
        tests/fixtures/P_01_cs_xMamin_20260804_180031_003.xle
git commit -m "feat(models): MeasurementRun container + P_01 five-def fixtures

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 3: `read_run` — assemble a run from its sibling files

**Files:**
- Modify: `src/camsizer_io/run_reader.py`
- Test: `tests/test_run_reader.py`

**Interfaces:**
- Consumes: `_parse_run_filename`, `_canonical_size_def`, `_TOKEN_TO_CANONICAL` (Task 1); `read_csv` (existing); `MeasurementRun`, `SIZE_DEF_ORDER` (Task 2).
- Produces: `read_run(path: str | Path) -> MeasurementRun`.
- Change: replace the temporary local `SIZE_DEF_ORDER` in `run_reader.py` with `from .models import MeasurementRun, SIZE_DEF_ORDER`.

- [ ] **Step 1: Write the failing test**

```python
# append to tests/test_run_reader.py
import warnings
from pathlib import Path

from camsizer_io import read_run
from camsizer_io.models import SIZE_DEF_ORDER

FIX = Path(__file__).parent / "fixtures"
_STAMP = "20260804_180031_003"


def test_read_run_finds_all_five_defs():
    mrun = read_run(FIX / f"P_01_cs_xc_min_{_STAMP}.xle")
    assert set(mrun.size_defs) == set(SIZE_DEF_ORDER)
    assert mrun.sample == "P_01_cs"
    assert mrun.timestamp == "20260804_180031"
    assert mrun.seq == "003"
    assert mrun["x_area"].summary["x50"] == pytest.approx(1.3419, abs=1e-4)
    assert mrun["xMa_min"].summary["x50"] == pytest.approx(1.0063, abs=1e-4)


def test_read_run_from_any_sibling_is_equivalent():
    a = read_run(FIX / f"P_01_cs_xc_min_{_STAMP}.xle")
    b = read_run(FIX / f"P_01_cs_xFemax_{_STAMP}.xle")
    assert a.size_defs == b.size_defs
    assert a.timestamp == b.timestamp


def test_read_run_partial_warns(tmp_path):
    # Only two of the five definitions present -> warn, still return them.
    for tok in ("xc_min", "x_area"):
        src = (FIX / f"P_01_cs_{tok}_{_STAMP}.xle").read_bytes()
        (tmp_path / f"P_01_cs_{tok}_{_STAMP}.xle").write_bytes(src)
    with pytest.warns(UserWarning):
        mrun = read_run(tmp_path / f"P_01_cs_xc_min_{_STAMP}.xle")
    assert set(mrun.size_defs) == {"xc_min", "x_area"}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_run_reader.py -k read_run -v`
Expected: FAIL — `ImportError: cannot import name 'read_run'`.

- [ ] **Step 3: Write minimal implementation**

In `src/camsizer_io/run_reader.py`: (a) delete the temporary `SIZE_DEF_ORDER` assignment; (b) add imports; (c) add `read_run`.

```python
# near the top, replacing the local SIZE_DEF_ORDER definition:
import warnings
from pathlib import Path

from .csv_reader import read_csv
from .models import MeasurementRun, SIZE_DEF_ORDER
```

```python
def read_run(path: str | Path) -> MeasurementRun:
    """Assemble a :class:`MeasurementRun` from any one of its export files.

    Given one size-definition export, this finds the sibling files that share
    its ``(sample, date, time, seq)`` identity, parses each, and groups them by
    canonical size definition (taken from each file's header ``size_model``).

    Args:
        path: Path to any one of the run's export files (e.g. an ``.xle``).

    Returns:
        A :class:`MeasurementRun` holding every size definition found.

    Raises:
        FileNotFoundError: If ``path`` does not exist.
        ValueError: If ``path``'s name is not a CAMSIZER run filename.

    Warnings:
        UserWarning: If fewer than five size definitions are found, if a
        filename token disagrees with its header, or on a duplicate definition.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(path)
    sample, _token, date, time, seq = _parse_run_filename(path.name)

    runs: dict[str, CamsizerRun] = {}
    for sibling in sorted(path.parent.glob(f"*{path.suffix}")):
        try:
            s_sample, s_token, s_date, s_time, s_seq = _parse_run_filename(sibling.name)
        except ValueError:
            continue
        if (s_sample, s_date, s_time, s_seq) != (sample, date, time, seq):
            continue
        run = read_csv(sibling)
        canon = _canonical_size_def(run.meta.size_model)
        expected = _TOKEN_TO_CANONICAL.get(s_token)
        if expected is not None and expected != canon:
            warnings.warn(
                f"{sibling.name}: filename token {s_token!r} implies {expected!r} "
                f"but header says {canon!r}; trusting header.",
                UserWarning,
                stacklevel=2,
            )
        if canon in runs:
            warnings.warn(
                f"Duplicate size definition {canon!r} in run "
                f"{sample}_{date}_{time}_{seq}; keeping {sibling.name}.",
                UserWarning,
                stacklevel=2,
            )
        runs[canon] = run

    if len(runs) < len(SIZE_DEF_ORDER):
        warnings.warn(
            f"Run {sample}_{date}_{time}_{seq}: found {len(runs)} size "
            f"definition(s) {sorted(runs)}, expected {len(SIZE_DEF_ORDER)}.",
            UserWarning,
            stacklevel=2,
        )

    return MeasurementRun(
        sample=sample,
        timestamp=f"{date}_{time}",
        seq=seq,
        runs=runs,
        source_dir=str(path.parent),
    )
```

Add `from .models import CamsizerRun` to the import block (used in the annotation) — combine as `from .models import CamsizerRun, MeasurementRun, SIZE_DEF_ORDER`.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_run_reader.py -v`
Expected: PASS (Task 1 cases still pass; new `read_run` cases pass).

- [ ] **Step 5: Commit**

```bash
git add src/camsizer_io/run_reader.py tests/test_run_reader.py
git commit -m "feat(run): read_run assembles a MeasurementRun from sibling files

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 4: `read_batch` + module-level `to_long`

**Files:**
- Modify: `src/camsizer_io/run_reader.py`
- Test: `tests/test_run_reader.py`

**Interfaces:**
- Consumes: `_parse_run_filename`, `read_run`, `MeasurementRun` (earlier tasks).
- Produces:
  - `read_batch(directory: str | Path, pattern: str = "*.xle") -> list[MeasurementRun]` — grouped by `(sample, date, time, seq)`, sorted by `(sample, timestamp, seq)`.
  - `to_long(runs: MeasurementRun | Iterable[MeasurementRun]) -> pd.DataFrame` — accepts a single run or an iterable; concatenates each run's `to_long()`.

- [ ] **Step 1: Write the failing test**

```python
# append to tests/test_run_reader.py
from camsizer_io import read_batch, to_long


def test_read_batch_groups_one_run():
    runs = read_batch(FIX, pattern="*.xle")
    assert len(runs) == 1
    assert set(runs[0].size_defs) == set(SIZE_DEF_ORDER)


def test_to_long_accepts_single_and_list():
    runs = read_batch(FIX, pattern="*.xle")
    one = to_long(runs[0])
    many = to_long(runs)
    assert len(one) == 5 * 1002
    assert len(many) == 5 * 1002
    assert list(many.columns)[:4] == ["sample", "timestamp", "seq", "size_def"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_run_reader.py -k "batch or to_long" -v`
Expected: FAIL — `ImportError: cannot import name 'read_batch'`.

- [ ] **Step 3: Write minimal implementation**

Add to `src/camsizer_io/run_reader.py` (extend imports with `from collections.abc import Iterable` and `import pandas as pd`):

```python
def read_batch(directory: str | Path, pattern: str = "*.xle") -> list[MeasurementRun]:
    """Group every matching export in a directory into measurements.

    Args:
        directory: Directory to scan.
        pattern: Glob for the export files (default ``*.xle``; use ``*.xld`` or
            ``*.csv`` for other export variants).

    Returns:
        One :class:`MeasurementRun` per ``(sample, date, time, seq)`` group,
        sorted by ``(sample, timestamp, seq)``. Files that do not match the run
        filename pattern are ignored.
    """
    directory = Path(directory)
    groups: dict[tuple[str, str, str, str], Path] = {}
    for f in sorted(directory.glob(pattern)):
        try:
            sample, _token, date, time, seq = _parse_run_filename(f.name)
        except ValueError:
            continue
        groups.setdefault((sample, date, time, seq), f)
    runs = [read_run(anchor) for anchor in groups.values()]
    return sorted(runs, key=lambda r: (r.sample, r.timestamp, r.seq))


def to_long(runs: MeasurementRun | Iterable[MeasurementRun]) -> pd.DataFrame:
    """Concatenate one or more measurements into a single tidy long table.

    Args:
        runs: A single :class:`MeasurementRun` or an iterable of them.

    Returns:
        The vertical concatenation of each run's :meth:`MeasurementRun.to_long`.
    """
    if isinstance(runs, MeasurementRun):
        return runs.to_long()
    frames = [r.to_long() for r in runs]
    if not frames:
        return pd.DataFrame(columns=_LONG_COLUMNS)
    return pd.concat(frames, ignore_index=True)
```

Add `from .models import CamsizerRun, MeasurementRun, SIZE_DEF_ORDER, _LONG_COLUMNS` (extend the existing import to include `_LONG_COLUMNS`).

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_run_reader.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/camsizer_io/run_reader.py tests/test_run_reader.py
git commit -m "feat(run): read_batch grouping + module-level to_long

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 5: `folk_ward` accepts a `MeasurementRun`

**Files:**
- Modify: `src/camsizer_io/stats.py`
- Test: `tests/test_stats.py`

**Interfaces:**
- Consumes: `MeasurementRun` (Task 2); `folk_ward`, `FolkWard`, `read_csv`, `read_run` (existing/earlier).
- Produces: `folk_ward(run: CamsizerRun | MeasurementRun, size_def: str = "xc_min") -> FolkWard`.
  - `CamsizerRun` path: unchanged results; `size_def` ignored.
  - `MeasurementRun` path: compute on `runs[size_def]`; if absent, use `.primary` and emit a `UserWarning`.

- [ ] **Step 1: Write the failing test**

```python
# append to tests/test_stats.py
import warnings

from camsizer_io import MeasurementRun, read_run

FIVE = Path(__file__).parent / "fixtures" / "P_01_cs_xc_min_20260804_180031_003.xle"


def test_folk_ward_measurement_defaults_to_xc_min():
    mrun = read_run(FIVE)
    from camsizer_io import folk_ward as fw
    got = fw(mrun)
    ref = fw(mrun["xc_min"])
    assert got.median_phi == pytest.approx(ref.median_phi, abs=1e-9)
    assert got.median_phi == pytest.approx(-0.1366, abs=1e-3)
    assert got.sorting_phi == pytest.approx(0.6598, abs=1e-3)


def test_folk_ward_measurement_size_def_override():
    from camsizer_io import folk_ward as fw
    mrun = read_run(FIVE)
    got = fw(mrun, size_def="x_area")
    assert got.d_mm["d50"] == pytest.approx(1.3419, rel=0.05)


def test_folk_ward_measurement_missing_def_falls_back_and_warns():
    from camsizer_io import folk_ward as fw, read_csv
    run = read_csv(Path(__file__).parent / "fixtures" / "P_01_cs_x_area_20260804_180031_003.xle")
    mrun = MeasurementRun(sample="P_01_cs", timestamp="20260804_180031",
                          seq="003", runs={"x_area": run})
    with pytest.warns(UserWarning):
        got = fw(mrun)  # xc_min absent -> fall back to x_area
    assert got.d_mm["d50"] == pytest.approx(1.3419, rel=0.05)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_stats.py -k measurement -v`
Expected: FAIL — `folk_ward()` rejects the `size_def` kwarg / mishandles a `MeasurementRun`.

- [ ] **Step 3: Write minimal implementation**

In `src/camsizer_io/stats.py`: extend the import to `from .models import CamsizerRun, MeasurementRun`, add `import warnings`, and change the `folk_ward` signature/head:

```python
def folk_ward(
    run: CamsizerRun | MeasurementRun, size_def: str = "xc_min"
) -> FolkWard:
    """Compute Folk & Ward graphical statistics for a run.

    Args:
        run: A parsed :class:`CamsizerRun`, or a :class:`MeasurementRun` (from
            which one size definition is selected).
        size_def: For a :class:`MeasurementRun`, the canonical size definition
            to use (default ``xc_min``, the sieve-comparable width). Ignored for
            a :class:`CamsizerRun`.

    Returns:
        A :class:`FolkWard` of phi-based statistics and the percentile
        diameters used.

    Raises:
        ValueError: If percentiles cannot be interpolated from the run.

    Warnings:
        UserWarning: If ``size_def`` is not present in a :class:`MeasurementRun`;
        the run's ``primary`` definition is used instead.
    """
    if isinstance(run, MeasurementRun):
        if size_def in run.runs:
            run = run.runs[size_def]
        else:
            chosen = run.primary
            warnings.warn(
                f"size_def {size_def!r} not in run {sorted(run.runs)}; "
                f"using primary instead.",
                UserWarning,
                stacklevel=2,
            )
            run = chosen
    # ... existing body unchanged, operating on the selected CamsizerRun ...
```

(The remainder of the function body — `pcts`, `d_mm`, phi math, `return FolkWard(...)` — is unchanged.)

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_stats.py -v`
Expected: PASS (existing `OK_sand` stats tests still pass; new `MeasurementRun` cases pass).

- [ ] **Step 5: Commit**

```bash
git add src/camsizer_io/stats.py tests/test_stats.py
git commit -m "feat(stats): folk_ward accepts a MeasurementRun (defaults xc_min)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 6: Public API exports + `read_export` alias + `.xle` coverage

**Files:**
- Modify: `src/camsizer_io/csv_reader.py` (add `read_export` alias + `.xle`/`.xld` docstring note)
- Modify: `src/camsizer_io/__init__.py` (export new names)
- Test: `tests/test_csv_reader.py`

**Interfaces:**
- Consumes: everything above.
- Produces: `read_export = read_csv` (alias); package exports `MeasurementRun`, `read_run`, `read_batch`, `to_long`, `read_export`, `SIZE_DEF_ORDER`.

- [ ] **Step 1: Write the failing test**

```python
# append to tests/test_csv_reader.py
XLE = Path(__file__).parent / "fixtures" / "P_01_cs_xc_min_20260804_180031_003.xle"


def test_read_csv_reads_xle_identically():
    run = read_csv(XLE)
    assert run.meta.size_model.startswith("xc_min")
    assert run.meta.method_file == "X_Fall_PPX.afg"
    assert run.summary["x50"] == pytest.approx(1.0993, abs=1e-4)


def test_public_api_exports():
    import camsizer_io as cs
    for name in ("MeasurementRun", "read_run", "read_batch", "to_long",
                 "read_export", "SIZE_DEF_ORDER"):
        assert hasattr(cs, name), name
    assert cs.read_export is cs.read_csv
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_csv_reader.py -k "xle or exports" -v`
Expected: FAIL — `read_export`/`read_run`/etc. not exported.

- [ ] **Step 3: Write minimal implementation**

In `src/camsizer_io/csv_reader.py`, after `read_csv` is defined, add:

```python
# `.xle` (point decimal) and `.xld` (comma decimal) exports share the CSV
# export's exact three-region layout, so read_csv reads them unchanged. The
# alias documents that these are supported too.
read_export = read_csv
```

Also add one sentence to the `read_csv` docstring `Args` note: `path` may be a `.csv`, `.xle`, or `.xld` export (identical format).

In `src/camsizer_io/__init__.py`, extend the imports and `__all__`:

```python
from .csv_reader import read_csv, read_export
from .models import CamsizerRun, MeasurementRun, ParticleRecord, RunMeta, SIZE_DEF_ORDER
from .run_reader import read_batch, read_run, to_long
```

Add `"read_export"`, `"MeasurementRun"`, `"SIZE_DEF_ORDER"`, `"read_run"`, `"read_batch"`, `"to_long"` to `__all__`.

- [ ] **Step 4: Run the full suite**

Run: `pytest -v`
Expected: PASS — all tests (existing `OK_sand`, X-Plorer, plus every new test) green.

- [ ] **Step 5: Commit**

```bash
git add src/camsizer_io/csv_reader.py src/camsizer_io/__init__.py tests/test_csv_reader.py
git commit -m "feat: export run API + read_export alias; cover .xle read

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 7: Documentation — README, format notes, fixtures README

**Files:**
- Modify: `README.md`
- Modify: `docs/format_notes.md`
- Modify: `tests/fixtures/README.md`

**Interfaces:**
- Consumes: the final public API.
- Produces: no code; verification is the full test suite still green + prose is accurate.

- [ ] **Step 1: Update `README.md`**

Add a "Multiple size definitions" subsection under the reliable-path usage:

````markdown
### Multiple size definitions

A measurement run can save up to five size definitions (`xc_min`, `x_area`,
`xFe_max`, `xFe_min`, `xMa_min`), one export file each. Read them as one run:

```python
import camsizer_io as cs

mrun = cs.read_run("P_01_cs_xc_min_20260804_180031_003.xle")  # any one sibling
mrun.size_defs                      # ['xc_min', 'x_area', 'xFe_max', ...]
mrun["x_area"].summary["x50"]       # 1.3419 (mm), area-equivalent diameter
cs.folk_ward(mrun)                  # Folk & Ward on xc_min (sieve-comparable)
cs.folk_ward(mrun, size_def="x_area")

runs = cs.read_batch("path/to/exports")   # list[MeasurementRun]
long = cs.to_long(runs)                    # tidy: sample × size_def × class
```

`read_csv`/`read_export` read the auto-saved `.xle` (point decimal) and `.xld`
(comma decimal) exports as well as the manual `.csv` — identical format.
````

- [ ] **Step 2: Update `docs/format_notes.md`**

Add a "Multiple size definitions" section documenting: the filename convention `<sample>_cs_<sizedef>_<YYYYMMDD>_<HHMMSS>_<seq>.<ext>`; the token↔canonical map; that the canonical key comes from the header `size_model`; and the fines dump-bin (first class `0.0000–0.0500 mm` holds sub-range fines, e.g. P_01 `PDN ≈ 265 000`, `p3 ≈ 0.004 %`, negligible mass, handled by the strictly-increasing-Q3 interpolation filter).

- [ ] **Step 3: Update `tests/fixtures/README.md`**

Record the five new fixtures: run `P_01_cs … 20260804_180031_003`, five `.xle` size definitions, sourced from `/Volumes/LEXAR/Camsizer/PPX/cs/` (CAMSIZER X2, dry X-Fall, sands). Note ground-truth x50 per definition.

- [ ] **Step 4: Verify suite still green**

Run: `pytest -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add README.md docs/format_notes.md tests/fixtures/README.md
git commit -m "docs: multi-size-definition usage, filename + dump-bin notes

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Self-Review

**Spec coverage:**
- `MeasurementRun` container → Task 2. ✅
- `read_run` → Task 3; `read_batch` → Task 4; `to_long` → Tasks 2 (method) + 4 (free fn). ✅
- Canonical from header, token cross-check, partial/duplicate warnings → Tasks 1 + 3. ✅
- Filename parse-from-right → Task 1. ✅
- `folk_ward` MeasurementRun dispatch, default xc_min, override, fallback warning → Task 5. ✅
- `read_csv` reads `.xle`; `read_export` alias → Task 6. ✅
- Fines dump-bin: handled (no special-casing) + documented + sanity-tested → Task 5 test (`sorting_phi` on real run) + Task 7 docs. ✅
- Fixtures committed with provenance → Task 2 (files) + Task 7 (README). ✅
- Non-goals (no `.rdf`/`.cdf`/`.xConAlp` change) → nothing touches them. ✅

**Placeholder scan:** No TBD/TODO; every code step has real code; every test asserts real ground-truth numbers. ✅

**Type consistency:** `SIZE_DEF_ORDER` lives in `models` (Task 2), imported by `run_reader` (Task 3 replaces the Task 1 stub) and `__init__` (Task 6) — the stub-then-repoint is called out explicitly in Tasks 1 and 3. `MeasurementRun` fields/props/methods match across Tasks 2–5. `folk_ward(run, size_def="xc_min")` signature consistent in Task 5 and README (Task 7). `_LONG_COLUMNS` defined in `models` (Task 2), imported by `run_reader` (Task 4). ✅

One known wrinkle handled deliberately: Task 1 defines a temporary `SIZE_DEF_ORDER` in `run_reader.py` so the leaf module tests standalone; Task 3 removes it in favor of the `models` import. This is stated in both tasks' Interfaces.
