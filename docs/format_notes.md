# CAMSIZER X2 file-format notes (reverse-engineered)

Findings from inspecting run `OK_sand_2_005` (Microtrac CAMSIZER X2, dry X-Fall,
19 s, exported 2026-07-28). **None of the binary formats below have a published
specification.** These notes record what was empirically observed so the
experimental decoder is auditable. Treat everything here as provisional.

## File set produced by one run

| Ext | Size (this run) | Role | Support in this package |
|-----|-----------------|------|-------------------------|
| `.csv` | 3.4 KB | Numerical export (UTF-16LE, tab-delimited) | **Parsed** (`read_csv`) |
| `.rdf` | 66 KB | Raw measurement data (doubles + delta-encoded runs) | Out of scope |
| `.cdf` | 73 KB | Class/distribution data (offset table + runs) | Out of scope |
| `.xIdx` | 1.0 MB | X-Plorer index (offset table into `.xConAlp`) | **Parsed** (`read_xplorer`) |
| `.xConAlp` | 61 MB | X-Plorer per-particle contour + alpha container | **Structural decode** (`read_xplorer`) |

All three binaries share the Retsch magic `43 21 34 24` (`C! 4$`) in their
header. Note: the `file(1)` utility misidentifies `.xConAlp` as a "Matlab v4
mat-file" — this is a magic-number collision, **not** a MATLAB file.

## `.csv` (supported, reliable)

UTF-16LE, CRLF, tab-delimited. Three regions:

1. **Header** (row 1): `<rdf name>`, `<method .afg>`, `<size model>`, `<date>`,
   `<time>`, `<duration>`.
2. **Summary block**: `label <TAB> value` rows — `x [mm] at Q3 = 10/50/90 %`,
   `SPAN3`, `U3`, `Q3 (SPHT=0.9) [%]` family, `Mean value SPHT3/Symm3/b/l3`.
3. **Size-class table**: introduced by a row whose first cell is `Size class`;
   columns `bin_lower, bin_upper, p3, Q3, SPHT3, Symm3, b_l3, PDN`.

For `OK_sand_2_005`: x10/x50/x90 = 0.2262 / 0.3099 / 0.4214 mm; `sum(PDN) = 4252`.

## `.xIdx` (supported, structural)

Flat table of **16-byte records**, four little-endian `uint32` fields each
(`63286` records in this run):

| Field | Observation | Interpretation |
|-------|-------------|----------------|
| 0 | mostly large, some `65536` | unconfirmed |
| 1 | `index * 65536` (0, 65536, 131072, …) | record counter |
| 2 | strictly increasing, `500504 … 61620826` | **byte offset into `.xConAlp`** |
| 3 | always `0` | unconfirmed / reserved |

Field 2 is the load-bearing one: it is strictly monotonic across the whole table
and stays within the `.xConAlp` file, so it cleanly partitions the container into
per-record blocks. This is validated structurally (`validate_structure`).

## `.xConAlp` (supported: descriptors validated, alpha raster raw)

Name reads as **Con**(tour) + **Alp**(ha).

- Bytes `0 .. offsets[0]` (here 500504) are a **preamble** holding ASCII metadata
  (`measure0`, the file name, etc.) then zero padding.
- Each record has a fixed layout:

  ```
  [2-byte flag] [16 × float32 descriptors = 64 B] [alpha raster = uint8 …]
  ```

- Per-record payload size varies (≈210 B – 11 KB); the variation is entirely in
  the trailing alpha raster (larger particles → larger silhouette).

### The 16-float descriptor header (validated)

Reading 16 `float32` at `offset + 2` yields a per-particle descriptor vector.
Across **all 63286 records** the columns are finite and bounded (no NaNs, zero
misaligned records), which confirms the alignment holds file-wide:

| Cols | Family | Range (this run) | Notes |
|------|--------|------------------|-------|
| 0–8 | size (mm) | 0.001 – 1.045 | three triples ordering widths < `xc_min` < Feret-max |
| 9 | area-like | 0 – 121 (99.9% < 3.5) | larger dynamic range; provisionally an area |
| 10–15 | shape (dimensionless) | 0.076 – 1.436 | `shape_5` exceeds 1 → behaves as **symmetry** |

**Cross-check against the CSV (ground truth `x50 = 0.3099` mm, xc_min model):**
the volume-weighted (`w = x³`) median of column 2 is **0.311 mm** — a near-exact
match — and the neighbouring size columns bracket it. Shape columns aggregate
into the reported mean-shape ranges. This validates the *extraction*; the exact
CAMSIZER name of each column is **inferred**, not confirmed against the software
(see `DESCRIPTOR_COLUMNS` in `xplorer.py`).

### The alpha raster (structure confirmed, dimensions not)

The trailing `uint8` bytes are the particle's grayscale silhouette: values
0–~250, ~30 % zeros (background). Row-stride autocorrelation shows strong 2-D
structure (corr ≈ 0.6–0.9 at particle-specific widths), so it is a real image —
but no explicit width/height field has been identified, so `read_xplorer`
returns `alpha` as a raw 1-D array rather than guessing a reshape.

### What is NOT established

- The exact CAMSIZER descriptor name of each of the 16 columns (only families
  and column 2 ≈ `xc_min` are validated).
- The width/height of the alpha raster.
- That one record == one PSD particle. The record count (`63286`) is the raw
  detection set and does **not** equal the CSV `PDN` total (`4252`).
- Whether the layout is stable across CAMSIZER software versions.

`read_xplorer` therefore exposes the **validated per-particle descriptor table**
(`to_dataframe` / `descriptor_matrix`) plus raw alpha bytes, and validates
structural self-consistency. For publication-grade morphometry from the
silhouette *images*, still prefer exporting from Particle X-Plorer.

## `.rdf` / `.cdf` (out of scope)

Header + a block of IEEE-754 doubles (summary statistics) followed by
delta-encoded contour/grayscale runs (`.rdf`) or a record-offset table then the
same runs (`.cdf`). Not decoded here — the CSV export carries the numbers we
need, and the CAMSIZER software is the authoritative reader.
