# camsizer-io

Read Microtrac **CAMSIZER X2** (dry-mode) outputs into tidy Python structures.

Two paths, deliberately unequal in trust:

| Path | Function | Status |
|------|----------|--------|
| CSV export → tidy PSD + shape tables | `read_csv` | **Reliable** — documented text format |
| Grain-size statistics (Folk & Ward) | `folk_ward` | **Reliable** |
| X-Plorer `.xIdx`/`.xConAlp` particle binaries | `read_xplorer` | ⚠️ **Experimental / reverse-engineered / unvalidated** |

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

`folk_ward` interpolates percentiles from the cumulative `Q3` curve, converts to
phi (`phi = -log2(mm)`), and returns the Folk & Ward (1957) graphical measures.
Percentiles use the sedimentological "percent coarser" convention.

## Usage — the experimental path (read the warning)

```python
run = cs.read_xplorer("OK_sand_2_005")     # .xIdx + .xConAlp beside this stem
report = cs.validate_structure(run)         # structural self-consistency only
rec = run.record(0)                         # raw float32 payload for one record
```

> ⚠️ **`read_xplorer` is reverse-engineered and unvalidated.** It performs a
> *structural* decode only: it reads the `.xIdx` byte-offset table, slices
> `.xConAlp` into per-record blocks, and exposes each block's raw `float32`
> payload. It does **not** separate contour vertices from the alpha (grayscale)
> raster, applies **no** physical calibration, and its record count is the raw
> detection set — it does **not** equal the CSV `PDN` particle total. Every call
> emits a `UserWarning`.
>
> **For real morphometry, export particle images from Particle X-Plorer** and
> process them with an image pipeline (scikit-image / OpenCV). See
> `docs/format_notes.md` for the byte-layout findings and
> `pparadox/docs/sop_camsizer_dry_psd.md` §10.2–10.3.

## Supported / not supported

- ✅ CAMSIZER X2 CSV export (dry mode), Folk & Ward stats
- ⚠️ `.xIdx`/`.xConAlp` structural decode (experimental)
- ❌ `.rdf`, `.cdf` decode; plotting; writing CAMSIZER formats; other instruments

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
