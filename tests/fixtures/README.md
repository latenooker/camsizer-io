# Test fixtures — run `OK_sand_2_005`

Real CAMSIZER X2 output from a single dry X-Fall run (2026-07-28), used as the
test fixture set.

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
