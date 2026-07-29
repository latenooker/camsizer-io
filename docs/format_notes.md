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

## `.xConAlp` (supported, structural only)

Name reads as **Con**(tour) + **Alp**(ha).

- Bytes `0 .. offsets[0]` (here 500504) are a **preamble** holding ASCII metadata
  (`measure0`, the file name, etc.).
- Each subsequent record = **2-byte flag** (`01 00`, sometimes `03 00`) + a
  little-endian `float32` payload.
- The leading floats of each record are small (~0.10–0.18), consistent with
  normalized contour coordinates; later values in the block are large/mixed,
  consistent with an interleaved **alpha (grayscale) raster**. The split point
  between contour and alpha is **not** resolved.
- Per-record payload size varies (≈210 B – 11 KB), i.e. larger particles carry
  more data.

### What is NOT established

- That one record == one PSD particle. The record count (`63286`) is the raw
  detection set and does **not** equal the CSV `PDN` total (`4252`); they measure
  different things.
- That the floats are calibrated to physical units.
- Where contour ends and alpha begins within a record.
- Whether the layout is stable across CAMSIZER software versions.

Because of the above, `read_xplorer` exposes raw per-record `float32` payloads
and validates only structural self-consistency. **For publication-grade
morphometry, export particle images from Particle X-Plorer** rather than relying
on this decode.

## `.rdf` / `.cdf` (out of scope)

Header + a block of IEEE-754 doubles (summary statistics) followed by
delta-encoded contour/grayscale runs (`.rdf`) or a record-offset table then the
same runs (`.cdf`). Not decoded here — the CSV export carries the numbers we
need, and the CAMSIZER software is the authoritative reader.
