# Design: multi-size-definition runs (v0.2)

**Date:** 2026-08-04
**Status:** Approved (pending implementation)
**Builds on:** `2026-07-28-camsizer-io-design.md`

## Purpose

The CAMSIZER X2 can save up to five **size definitions** per measurement, each as
a separate export file. The `pparadox` workflow now runs all five (`xc_min`,
`x_area`, `xFe_max`, `xFe_min`, `xMa_min`). One measurement therefore produces
five per-size-definition `.xle` files instead of a single `.csv`. This adds a
grouping-and-aggregation layer on top of the existing reader so a measurement is
read as one object exposing all five size definitions, plus a tidy long-format
batch export for downstream analysis.

## Background: the input files

Each size-definition file is the **same** three-region format `read_csv` already
parses (UTF-16LE, CRLF, tab-delimited: header row, `label <TAB> value` summary
block, `Size class` table). The only per-file differences are the header
`size_model` string and what the size axis (`bin_lower`/`bin_upper`) means. The
auto-saved `.xle` uses a point decimal; `.xld` uses a comma decimal; `_to_float`
already tolerates both.

**Filename convention** (observed on real runs):

```
<sample>_cs_<sizedef>_<YYYYMMDD>_<HHMMSS>_<seq>.<ext>
P_01_cs_xc_min_20260804_180031_003.xle
```

All five size definitions of one measurement share the same
`<YYYYMMDD>_<HHMMSS>_<seq>` suffix, so `(sample, date, time, seq)` is the run
grouping key. Filename tokens map to canonical size-definition keys (the first
word of the header `size_model`, which is authoritative):

| Filename token | Header `size_model`           | Canonical key |
|----------------|-------------------------------|---------------|
| `x_area`       | `x_area with shape parameter …`  | `x_area`   |
| `xc_min`       | `xc_min with shape parameter …`  | `xc_min`   |
| `xFemax`       | `xFe_max with shape parameter …` | `xFe_max`  |
| `xFemin`       | `xFe_min with shape parameter …` | `xFe_min`  |
| `xMamin`       | `xMa_min with shape parameter …` | `xMa_min`  |

Because tokens like `x_area` contain underscores, the filename is parsed **from
the right**: the last three underscore-separated fields are `date` (8 digits),
`time` (6 digits), `seq`; everything between `_cs_` and those is the size-def
token.

## Scope

**In scope**

- `MeasurementRun` container composing up to five `CamsizerRun`s.
- `read_run(path)` — from any one of a run's files, discover the siblings and
  assemble a `MeasurementRun`.
- `read_batch(dir, pattern="*.xle")` — group every matching file into
  `MeasurementRun`s.
- `to_long(runs_or_run)` — one tidy long-format DataFrame across runs × size
  definitions × size classes.
- `folk_ward` accepts a `MeasurementRun` (defaults to `xc_min`, overridable).
- `read_csv` documented as reading `.xle`/`.xld` too, with a clearer alias
  `read_export`.

**Out of scope (unchanged from v0.1, YAGNI)**

- `.rdf`/`.cdf` decode. The X-Plorer `.xIdx`/`.xConAlp` path is **per-run, not
  per-size-definition** — the five size definitions are re-binnings of the same
  particle set, and `.xConAlp` already carries the per-particle multi-size
  descriptor vector — so it needs no change here.
- Plotting, writing/converting CAMSIZER formats, multi-instrument support.

## Architecture

New file `src/camsizer_io/run_reader.py` (single purpose: grouping + assembly).
`CamsizerRun` is unchanged. `MeasurementRun` composes five of them.

```
src/camsizer_io/
  models.py       + MeasurementRun (composes dict[str, CamsizerRun])
  csv_reader.py   read_csv (unchanged behavior; + read_export alias, .xle docs)
  run_reader.py   NEW: read_run, read_batch, to_long, filename parsing
  stats.py        folk_ward accepts MeasurementRun (defaults xc_min)
  xplorer.py      unchanged
```

### `MeasurementRun` (models.py)

```python
@dataclass
class MeasurementRun:
    sample: str                       # e.g. "P_01_cs"
    timestamp: str                    # "20260804_180031"
    seq: str                          # "003"
    runs: dict[str, CamsizerRun]      # canonical size-def key -> run
    source_dir: str | None = None
```

- `size_defs -> list[str]` — canonical keys present, in canonical order
  (`xc_min, x_area, xFe_max, xFe_min, xMa_min`), unknown keys appended.
- `__getitem__(key)` / `by_size_def` — access a `CamsizerRun` by canonical key.
- `primary -> CamsizerRun` — `xc_min` if present, else the first present def.
- `to_long() -> DataFrame` — this run's classes across its size defs, columns
  `[sample, timestamp, seq, size_def, bin_lower, bin_upper, p3, Q3, SPHT3,
  Symm3, b_l3, PDN]`.

### Readers (run_reader.py)

- `read_run(path)` — `path` is any one existing file of the run (any of its
  five size-def exports). Parse that filename → `(sample, date, time, seq)`;
  glob the directory for siblings sharing that key; `read_csv` each; key by
  header-derived canonical
  size-def; cross-check against the filename token (warn on mismatch); warn if
  fewer than five size defs are found (partial run, not an error).
- `read_batch(dir, pattern="*.xle") -> list[MeasurementRun]` — glob, group by
  `(sample, date, time, seq)`, assemble each. Deterministic order (sorted by
  sample then timestamp then seq).
- `to_long(runs_or_run) -> DataFrame` — accepts a single `MeasurementRun` or a
  list; concatenates each run's `to_long()`.

### Folk & Ward (stats.py)

`folk_ward(run, size_def="xc_min")`:
- `CamsizerRun` → unchanged results; `size_def` is ignored on this path (a
  single-definition run has nothing to select). Back-compat preserved: existing
  `folk_ward(camsizer_run)` calls behave identically.
- `MeasurementRun` → compute on `runs[size_def]`; if `size_def` absent, fall back
  to `.primary` with a `UserWarning`.

Dispatch by `isinstance`.

## Data flow

```
dir of .xle ──read_batch──► [MeasurementRun, …] ──to_long──► tidy long DataFrame
one .xle    ──read_run───►  MeasurementRun          │
                              ├ runs["xc_min"] ──folk_ward──► FolkWard
                              ├ runs["x_area"]  (PSD for laser-diffraction cmp)
                              └ runs["xFe_max"] …
```

## Error handling

- Missing file / unreadable → propagate `FileNotFoundError` (as `read_csv` does).
- Filename that does not match the run pattern → `ValueError` naming the file.
- Header size-def token ≠ filename token → `UserWarning`, trust the header.
- Partial run (<5 size defs) → `UserWarning`, return what was found.
- Duplicate size-def within one run group → `UserWarning`, keep the last, list
  the conflicting files.

## The fines dump-bin

Real X-Fall exports pile sub-measurement-range fines into the first size class
(e.g. P_01 `0.0000–0.0500 mm`, `PDN ≈ 265 000`, `p3 ≈ 0.004 %`). The mass
fraction is negligible, and `percentile_mm` already restricts interpolation to
the strictly-increasing part of the `Q3` curve, so the flat leading region is
handled correctly with no special-casing. Documented in `format_notes.md`; a
test asserts `folk_ward` on a real five-def run returns sane, well-sorted-sand
values.

## Validation / ground truth

- `read_run` on the P_01 fixture finds exactly five size defs with canonical
  keys `{xc_min, x_area, xFe_max, xFe_min, xMa_min}`.
- `folk_ward(measurement_run)` (default `xc_min`) equals
  `folk_ward(read_csv(P_01 xc_min .xle))`.
- `to_long` row count == sum of per-size-def class counts; column set fixed.
- `read_csv` reads a `.xle` identically to a `.csv` (same schema).

## Fixtures / provenance

Commit the five real `.xle` files of one P_01 run (~95 KB each, <0.5 MB total)
to `tests/fixtures/`, sourced from
`/Volumes/LEXAR/Camsizer/PPX/cs/`. Record source and run identity in
`tests/fixtures/README.md`. No large binary is added (the `.xConAlp` path is
untouched).

## Documentation

- `README.md` — add the multi-size-definition usage block (`read_run`,
  `read_batch`, `to_long`, `folk_ward(size_def=…)`).
- `docs/format_notes.md` — filename convention, the size-def token↔header map,
  and the fines dump-bin.
- This spec committed under `docs/superpowers/specs/`.
