# Test fixtures

## `OK_sand_2_005` run

Real CAMSIZER X2 output from a single dry X-Fall run (2026-07-28), used as the
single-size-definition test fixture set.

| File | Committed? | Used by |
|------|-----------|---------|
| `OK_sand_2_005.csv` | yes (3.4 KB) | `test_csv_reader`, `test_stats` |
| `OK_sand_2_005.rdf` | yes (66 KB) | reference only |
| `OK_sand_2_005.cdf` | yes (73 KB) | reference only |
| `OK_sand_2_005.xIdx` | yes (1.0 MB) | `test_xplorer` (real-file test) |
| `OK_sand_2_005.xConAlp` | **no — git-ignored (61 MB)** | `test_xplorer::test_real_run_structural_consistency` (opt-in) |

The `.xConAlp` blob is too large to commit. `read_xplorer` is otherwise tested
against a synthetic pair built inside `test_xplorer.py`. To run the opt-in real
test, drop the original `.xConAlp` back into this directory; the source of record
is:

```
pparadox/data/lab/camsizer/OK_sand_2_005.xConAlp
```

## `P_01_cs … 20260804_180031_003` run

Real CAMSIZER X2 output from a single dry X-Fall run with five size definitions
(2026-08-04), used to test multi-size-definition reading and tidy export.

**Source:** `/Volumes/LEXAR/Camsizer/PPX/cs/` (CAMSIZER X2, dry X-Fall, sands)

**Fixtures** (five `.xle` files, one per size definition):

| File | Committed? | Size def | x50 (mm) | Used by |
|------|-----------|----------|----------|---------|
| `P_01_cs_xc_min_20260804_180031_003.xle` | yes | `xc_min` | 1.0993 | `test_run_reader`, `test_batch_reader` |
| `P_01_cs_x_area_20260804_180031_003.xle` | yes | `x_area` | 1.3419 | `test_run_reader`, `test_batch_reader` |
| `P_01_cs_xFemax_20260804_180031_003.xle` | yes | `xFe_max` | 1.7783 | `test_run_reader`, `test_batch_reader` |
| `P_01_cs_xFemin_20260804_180031_003.xle` | yes | `xFe_min` | 1.1386 | `test_run_reader`, `test_batch_reader` |
| `P_01_cs_xMamin_20260804_180031_003.xle` | yes | `xMa_min` | 1.0063 | `test_run_reader`, `test_batch_reader` |

All five files share the `20260804_180031_003` timestamp/sequence suffix, which
groups them as a single run. Ground-truth x50 values are used to validate size
definition reading and the `to_long` tidy export.
