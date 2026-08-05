# camsizer-io

Read Microtrac **CAMSIZER X2** (dry-mode) outputs into tidy Python structures.

Two paths, deliberately unequal in trust:

| Path | Function | Status |
|------|----------|--------|
| CSV export → tidy PSD + shape tables | `read_csv` | **Reliable** — documented text format |
| Grain-size statistics (Folk & Ward) | `folk_ward` | **Reliable** |
| Per-particle size/shape from `.xIdx`/`.xConAlp` | `read_xplorer` → `to_dataframe` | ⚠️ **Experimental / reverse-engineered** (descriptor *extraction* validated vs CSV; per-column names inferred) |

The `.rdf` and `.cdf` raw binaries are intentionally **out of scope** — there is
no published spec and the software is their authoritative reader.

## Install

```bash
pip install -e ".[dev]"
```

Requires Python ≥ 3.11 (numpy, pandas).

## Usage — the reliable path

```python
import camsizer_io as cs

run = cs.read_csv("OK_sand_2_005.csv")
run.meta.size_model          # 'xc_min with shape parameter 1.0000'
run.summary["x50"]           # 0.3099  (mm)
run.particle_count           # 4252    (sum of PDN)
run.psd                      # DataFrame: bin_lower, bin_upper, p3, Q3, SPHT3, Symm3, b_l3, PDN

fw = cs.folk_ward(run)
fw.median_phi, fw.sorting_phi, fw.skewness, fw.kurtosis
```

`read_csv` parses the UTF-16LE, tab-delimited export the CAMSIZER X2 software
writes: header metadata, the scalar summary block (x10/x50/x90, SPAN3, U3, shape
means), and the per-size-class table.

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

`folk_ward` interpolates percentiles from the cumulative `Q3` curve, converts to
phi (`phi = -log2(mm)`), and returns the Folk & Ward (1957) graphical measures.
Percentiles use the sedimentological "percent coarser" convention.

### Re-binning to a common grid

The instrument reports the volume distribution on ~1000 fine classes — too noisy
to read as a density and awkward to compare across runs with different class
files. `rebin` re-bins a run onto arbitrary size-class edges *from the cumulative
`Q3` curve*, so it conserves mass (no histogram re-assignment):

```python
edges = cs.log_edges(0.08, 20, 100)        # 100 log-spaced bins
df = cs.rebin(run, edges)                   # bin_lower/upper/center, p3, Q3, density
```

`p3` is the exact volume % in each bin, and `density` is `p3` per `log10` size
interval — the natural PDF on a log axis, where the area under the curve equals
the covered volume percent. Only the size distribution is re-binned (not the
class-mean shape characteristics).

## Usage — the experimental path (read the warning)

Each `.xConAlp` record is `[2-byte flag][16 float32 descriptors][alpha raster]`.
The 16-value descriptor header is a **per-particle size/shape vector**, so you
get a table of every detected particle:

```python
run = cs.read_xplorer("OK_sand_2_005")     # .xIdx + .xConAlp beside this stem
cs.validate_structure(run).ok              # structural self-consistency
df = run.to_dataframe()                     # (n_particles, 16): size_* (mm), shape_*
rec = run.record(0)                         # rec.descriptors (16,), rec.alpha (uint8 raster)
```

> ⚠️ **`read_xplorer` is reverse-engineered.** What is *validated*: the
> descriptor **extraction** — across all records the columns are finite and
> in-family, and the volume-weighted x50 of the `xc_min`-family column
> reproduces the CSV's reported value (0.311 vs 0.3099 mm). What is **not**
> confirmed: the exact CAMSIZER name of each of the 16 columns (families and
> `size_2` ≈ `xc_min` are validated; the rest are inferred), the width/height of
> the alpha raster (returned raw/1-D), and that one record equals one PSD
> particle (the record count is the raw detection set, ≠ the CSV `PDN` total).
> Every call emits a `UserWarning`.
>
> **For publication-grade morphometry from the silhouette *images*, export from
> Particle X-Plorer** and process with an image pipeline (scikit-image / OpenCV).
> See `docs/format_notes.md` for the byte-layout findings and
> `pparadox/docs/sop_camsizer_dry_psd.md` §10.2–10.3.

## Supported / not supported

- ✅ CAMSIZER X2 CSV export (dry mode), Folk & Ward stats
- ⚠️ `.xIdx`/`.xConAlp` per-particle descriptor table (extraction validated; column names inferred) + raw alpha rasters
- ❌ `.rdf`, `.cdf` decode; reshaping/calibrating alpha images; plotting; writing CAMSIZER formats; other instruments

## Tests

```bash
pytest
```

The small real fixtures (`.csv`/`.rdf`/`.cdf`/`.xIdx`) from run `OK_sand_2_005`
are committed. The paired 60+ MB `.xConAlp` is **git-ignored**; the decoder is
tested against a synthetic fixture, plus an opt-in test that runs against the
real `.xConAlp` when it is present locally.

## License

MIT
