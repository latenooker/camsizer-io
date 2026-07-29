# Design: camsizer-io (v0.1)

**Date:** 2026-07-28
**Status:** Implemented

## Purpose

A narrow Python package to read Microtrac CAMSIZER X2 (dry-mode) outputs into
tidy Python structures. One reliable path (CSV export) and one clearly-fenced
experimental path (X-Plorer particle binaries). No analysis beyond standard
grain-size statistics. Sister repo to `pparadox`, which consumes it.

## Scope

**In scope**

- `read_csv` — parse the UTF-16 CSV export → `CamsizerRun` (metadata, per-size-
  class PSD + shape table, scalar summary).
- `folk_ward` — Folk & Ward (1957) graphical statistics from the `Q3` curve.
- `read_xplorer` — **experimental, reverse-engineered** structural decoder for
  `.xIdx`/`.xConAlp`: index offset table → per-record raw `float32` payloads,
  with structural validation and a loud `UserWarning`.

**Out of scope (YAGNI)**

- `.rdf`/`.cdf` decode (no spec; software is the authoritative reader).
- Semantic contour/alpha separation or physical calibration of X-Plorer data.
- Plotting, GUI, writing/converting CAMSIZER formats, multi-instrument support.

## Architecture

`src/` layout, setuptools, Python ≥ 3.11, numpy + pandas, pytest.

```
src/camsizer_io/
  __init__.py     public API
  models.py       CamsizerRun, RunMeta, ParticleRecord (dataclasses)
  csv_reader.py   read_csv  — RELIABLE
  stats.py        folk_ward, percentile_mm
  xplorer.py      read_xplorer, validate_structure — EXPERIMENTAL
docs/format_notes.md   reverse-engineering findings
tests/          real OK_sand_2_005 fixtures (+ synthetic X-Plorer pair)
```

### Reliable core

`read_csv` handles the three CSV regions (header, summary block, size-class
table) tolerantly (comma decimals, stray whitespace, blank rows). `folk_ward`
interpolates percentiles from the cumulative `Q3` curve, mapping Folk & Ward
"percent coarser" percentiles to `Q3 = 100 − p` percent-passing, converts to phi,
and returns mean/median/sorting/skewness/kurtosis.

### Experimental path

`read_xplorer` reads the `.xIdx` 16-byte-record offset table (field 2 = byte
offset into `.xConAlp`), slices the container into per-record blocks (2-byte flag
+ `float32` payload), and exposes raw payloads lazily. `validate_structure`
checks only what is checkable without ground truth: offsets strictly increasing
and in-bounds. The record count is **not** asserted to equal the CSV `PDN` total
(different quantities). Ships real (not a stub) because the *structural* decode
is self-consistent and validated; the *semantic* layer is explicitly disclaimed.

## Validation / ground truth

- CSV: `x50 = 0.3099` mm, `sum(PDN) = 4252` — asserted in tests.
- Folk & Ward: interpolated D50 ≈ reported x50; well-sorted-sand sanity bounds.
- X-Plorer: synthetic round-trip + opt-in real-file structural test
  (`n_records == 63286`, offsets monotonic and in-bounds).

## Provenance

README states the CSV path is supported and the binaries are reverse-engineered/
unvalidated; `docs/format_notes.md` records byte-layout findings; the
`OK_sand_2_005.*` run is the committed fixture (61 MB `.xConAlp` git-ignored,
sourced from `pparadox/data/lab/camsizer/`).
