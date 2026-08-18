"""Command-line interface for camsizer-io.

A thin argparse wiring layer over the public reader API — no business logic
lives here. Three subcommands, each mapping to an existing library entry point:

* ``read <csv>``   — :func:`read_csv`; prints the scalar summary (add
  ``--stats`` for Folk & Ward), and with ``-o`` writes the per-class PSD table.
* ``run <file>``   — :func:`read_run` → :func:`to_long`; the tidy long table
  for one multi-size-definition measurement.
* ``batch <dir>``  — :func:`read_batch` → :func:`to_long`; every measurement
  in a directory, concatenated.

With ``-o/--output`` a table is written via :func:`write_table`
(``-f/--format`` ``csv`` or ``parquet``); without it a short preview goes to
stdout.
"""

from __future__ import annotations

import argparse
from collections.abc import Sequence

import pandas as pd

from .csv_reader import read_csv
from .run_reader import read_batch, read_run, to_long
from .stats import folk_ward
from .writers import write_table


def _build_parser() -> argparse.ArgumentParser:
    """Construct the top-level argument parser and its subcommands."""
    parser = argparse.ArgumentParser(
        prog="camsizer-io",
        description="Read Microtrac CAMSIZER X2 dry-mode exports into tidy tables.",
    )
    sub = parser.add_subparsers(dest="command", metavar="{read,run,batch}")

    p_read = sub.add_parser("read", help="read one CSV export; print/write its PSD")
    p_read.add_argument("csv", help="path to a CAMSIZER CSV export")
    p_read.add_argument(
        "--stats", action="store_true", help="also print Folk & Ward statistics"
    )
    _add_output_flags(p_read)
    p_read.set_defaults(func=_cmd_read)

    p_run = sub.add_parser("run", help="read a multi-size-definition run to long form")
    p_run.add_argument("file", help="any one sibling export of the run")
    _add_output_flags(p_run)
    p_run.set_defaults(func=_cmd_run)

    p_batch = sub.add_parser("batch", help="read a directory of exports to long form")
    p_batch.add_argument("directory", help="directory of CAMSIZER exports")
    p_batch.add_argument(
        "--pattern", default="*.xle", help="glob for export files (default: *.xle)"
    )
    _add_output_flags(p_batch)
    p_batch.set_defaults(func=_cmd_batch)

    return parser


def _add_output_flags(parser: argparse.ArgumentParser) -> None:
    """Attach the shared ``-o/--output`` and ``-f/--format`` flags."""
    parser.add_argument(
        "-o", "--output", help="write the table here (extension added if missing)"
    )
    parser.add_argument(
        "-f",
        "--format",
        default="csv",
        choices=("csv", "parquet"),
        help="output format when writing (default: csv)",
    )


def _emit(df: pd.DataFrame, args: argparse.Namespace, label: str) -> None:
    """Write ``df`` to ``args.output`` if set, else print a short preview."""
    if args.output:
        path = write_table(df, args.output, args.format)
        print(f"wrote {label} -> {path} ({len(df)} rows)")
    else:
        print(f"{label}: {len(df)} rows")
        print(df.head().to_string(index=False))


def _cmd_read(args: argparse.Namespace) -> int:
    run = read_csv(args.csv)
    print(f"particles: {run.particle_count}")
    for key, value in run.summary.items():
        print(f"{key}: {value}")
    if args.stats:
        fw = folk_ward(run)
        print("--- Folk & Ward ---")
        print(f"mean_phi: {fw.mean_phi}")
        print(f"median_phi: {fw.median_phi}")
        print(f"sorting_phi: {fw.sorting_phi}")
        print(f"skewness: {fw.skewness}")
        print(f"kurtosis: {fw.kurtosis}")
    if args.output:
        path = write_table(run.psd, args.output, args.format)
        print(f"wrote psd -> {path} ({len(run.psd)} rows)")
    return 0


def _cmd_run(args: argparse.Namespace) -> int:
    _emit(to_long(read_run(args.file)), args, "long")
    return 0


def _cmd_batch(args: argparse.Namespace) -> int:
    runs = read_batch(args.directory, pattern=args.pattern)
    _emit(to_long(runs), args, "long")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    """Entry point.

    Args:
        argv: Argument list (defaults to ``sys.argv[1:]``).

    Returns:
        Process exit code: ``0`` on success, ``2`` if no subcommand was given.
    """
    parser = _build_parser()
    args = parser.parse_args(argv)
    if not getattr(args, "command", None):
        parser.print_help()
        return 2
    return int(args.func(args))


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
