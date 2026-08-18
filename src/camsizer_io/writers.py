"""Write tidy camsizer-io tables to disk.

Two formats, matching the package's minimal footprint:

* ``"csv"`` — always available (via pandas). A portable, inspectable text
  format; pandas' own type inference recovers dtypes on read-back.
* ``"parquet"`` — lossless and dtype-preserving, but only if ``pyarrow`` is
  installed. It is an optional dependency, so :func:`write_table` raises a
  clear :class:`ImportError` when ``fmt="parquet"`` is requested without it.

This is the on-disk counterpart to the DataFrames returned by
:func:`camsizer_io.to_long` and :attr:`CamsizerRun.psd`; the readers stay the
authoritative entry points, so there is deliberately no ``read_table`` here.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

_EXTENSIONS: dict[str, str] = {"csv": ".csv", "parquet": ".parquet"}


def _with_extension(path: Path, fmt: str) -> Path:
    """Return ``path`` carrying the canonical extension for ``fmt``.

    Args:
        path: Target path, with or without the format's extension.
        fmt: One of ``"csv"`` or ``"parquet"``.

    Returns:
        ``path`` unchanged if it already ends with the right extension,
        otherwise ``path`` with that extension appended.

    Raises:
        ValueError: If ``fmt`` is not a supported format.
    """
    try:
        ext = _EXTENSIONS[fmt]
    except KeyError as exc:
        raise ValueError(
            f"Unsupported table format: {fmt!r} (expected one of "
            f"{sorted(_EXTENSIONS)})."
        ) from exc
    return path if path.suffix == ext else path.with_name(path.name + ext)


def write_table(df: pd.DataFrame, path: str | Path, fmt: str = "csv") -> Path:
    """Write a DataFrame to disk in a supported table format.

    Args:
        df: The table to write.
        path: Destination path; the canonical extension for ``fmt`` is
            appended if not already present.
        fmt: ``"csv"`` (default, always available) or ``"parquet"``
            (requires ``pyarrow``).

    Returns:
        The path actually written, including the canonical extension.

    Raises:
        ValueError: If ``fmt`` is not a supported format.
        ImportError: If ``fmt="parquet"`` but ``pyarrow`` is not installed.
    """
    out = _with_extension(Path(path), fmt)
    if fmt == "csv":
        df.to_csv(out, index=False)
    else:  # parquet — validated by _with_extension above
        try:
            import pyarrow  # noqa: F401
        except ModuleNotFoundError as exc:
            raise ImportError(
                "Writing parquet requires the optional 'pyarrow' dependency; "
                "install it or use fmt='csv'."
            ) from exc
        df.to_parquet(out, index=False)
    return out
