"""Data loaders for timing traces and secret labels.

Supports CSV and NumPy (.npz) formats with automatic detection of
pre-aggregated vs. raw (multi-repeat) trace layouts.
"""

from __future__ import annotations

import pathlib
from typing import Dict, List, NamedTuple, Optional, Sequence, Union

import numpy as np
import pandas as pd
from scipy import stats


# ---------------------------------------------------------------------------
# Result container
# ---------------------------------------------------------------------------

class DataBundle(NamedTuple):
    """Standardised container returned by every loader.

    Attributes
    ----------
    fixed_timings : np.ndarray
        1-D array of per-key timing values for the *fixed* group.
    random_timings : np.ndarray
        1-D array of per-key timing values for the *random* group.
    per_key_features : np.ndarray
        2-D array (n_keys, n_features) of aggregated statistics per key.
        Feature columns: min, median, mean, std, iqr, p99, kurtosis, skew.
    per_key_labels : Optional[Dict[str, np.ndarray]]
        Mapping from target name (e.g. ``"sk_lsb"``) to a 1-D int/float
        array aligned with the rows of *per_key_features*.
    metadata : Dict
        Free-form metadata (e.g. source file, n_repeats, column names).
    """

    fixed_timings: np.ndarray
    random_timings: np.ndarray
    per_key_features: np.ndarray
    per_key_labels: Optional[Dict[str, np.ndarray]]
    metadata: Dict


# Canonical order of the eight aggregate features.
FEATURE_NAMES: List[str] = [
    "min", "median", "mean", "std", "iqr", "p99", "kurtosis", "skew",
]


# ---------------------------------------------------------------------------
# Aggregation helpers
# ---------------------------------------------------------------------------

def _aggregate_per_key(df: pd.DataFrame,
                       key_col: str = "key_id",
                       value_col: str = "timing_ticks") -> pd.DataFrame:
    """Compute per-key summary statistics from raw traces.

    Parameters
    ----------
    df : pd.DataFrame
        Raw trace data with at least *key_col* and *value_col*.
    key_col : str
        Column identifying the key (group variable).
    value_col : str
        Column containing raw timing measurements.

    Returns
    -------
    pd.DataFrame
        One row per key with columns for each aggregate feature.
    """

    def _agg(group: pd.Series) -> pd.Series:
        arr = group.values
        q25, q75 = np.percentile(arr, [25, 75])
        return pd.Series({
            "min": np.min(arr),
            "median": np.median(arr),
            "mean": np.mean(arr),
            "std": np.std(arr, ddof=1) if len(arr) > 1 else 0.0,
            "iqr": q75 - q25,
            "p99": np.percentile(arr, 99),
            "kurtosis": float(stats.kurtosis(arr, fisher=True))
                        if len(arr) >= 4 else 0.0,
            "skew": float(stats.skew(arr)) if len(arr) >= 3 else 0.0,
        })

    return df.groupby(key_col)[value_col].apply(_agg).unstack()


def _is_preaggregated(df: pd.DataFrame,
                      key_col: str = "key_id") -> bool:
    """Return ``True`` when *df* has at most one row per key."""
    if key_col not in df.columns:
        return True  # no key column -> treat as pre-aggregated
    return df[key_col].nunique() == len(df)


# ---------------------------------------------------------------------------
# CSV loader
# ---------------------------------------------------------------------------

def load_csv(
    trace_path: Union[str, pathlib.Path],
    label_path: Optional[Union[str, pathlib.Path]] = None,
    fixed_key_id: Optional[int] = 0,
    key_col: str = "key_id",
    repeat_col: str = "repeat_id",
    value_col: str = "timing_ticks",
    target_cols: Optional[Sequence[str]] = None,
) -> DataBundle:
    """Load timing traces (and optional labels) from CSV files.

    Parameters
    ----------
    trace_path : str or Path
        CSV containing at least *value_col*. May also have *key_col*,
        *repeat_col*, and secret label columns.
    label_path : str or Path, optional
        Separate CSV with per-key secret labels.
    fixed_key_id : int, optional
        Value of *key_col* that identifies fixed-key traces. Defaults to 0.
    key_col, repeat_col, value_col : str
        Column names for the key identifier, repeat index, and raw timing.
    target_cols : sequence of str, optional
        Label columns to extract. If ``None``, auto-detected as any column
        not in ``{key_col, repeat_col, value_col}``.

    Returns
    -------
    DataBundle
    """
    trace_path = pathlib.Path(trace_path)
    df = pd.read_csv(trace_path)

    # --- Derive common targets if not present -----------------------------
    if "sk_lsb" not in df.columns and "sk_byte0" in df.columns:
        df["sk_lsb"] = df["sk_byte0"] % 2
    if "msg_hw_parity" not in df.columns and "message_hw" in df.columns:
        df["msg_hw_parity"] = df["message_hw"] % 2

    # --- Auto-detect column names if defaults don't match -----------------
    if value_col not in df.columns:
        timing_candidates = [c for c in df.columns
                             if "timing" in c.lower() or "cycles" in c.lower()
                             or "ticks" in c.lower()]
        if timing_candidates:
            value_col = timing_candidates[0]
        else:
            raise KeyError(
                f"No timing column found. Columns: {list(df.columns)}. "
                f"Pass --value-col explicitly."
            )
    if repeat_col not in df.columns:
        repeat_candidates = [c for c in df.columns
                             if "repeat" in c.lower()]
        if repeat_candidates:
            repeat_col = repeat_candidates[0]

    # --- Auto-detect label columns in the trace file ----------------------
    reserved = {key_col, repeat_col, value_col}
    inline_label_cols = [c for c in df.columns if c not in reserved]

    # --- Pre-aggregated vs. raw -------------------------------------------
    if _is_preaggregated(df, key_col):
        # Each row is already one key.  Use the value column as the "mean"
        # feature and build a trivial feature matrix.
        per_key = df.copy()
        features = df[value_col].values.reshape(-1, 1)
        # Pad to 8 features (the rest are zero / NaN).
        pad = np.zeros((features.shape[0], len(FEATURE_NAMES) - 1))
        features = np.hstack([features, pad])
    else:
        per_key = _aggregate_per_key(df, key_col, value_col)
        per_key = per_key.reset_index()
        features = per_key[FEATURE_NAMES].values

    # --- Fixed / random split ---------------------------------------------
    if key_col in df.columns:
        fixed_mask = df[key_col] == fixed_key_id
        fixed_timings = df.loc[fixed_mask, value_col].values.astype(np.float64)
        random_timings = df.loc[~fixed_mask, value_col].values.astype(np.float64)
    else:
        # Without a key column, split 50/50.
        n = len(df)
        fixed_timings = df[value_col].values[:n // 2].astype(np.float64)
        random_timings = df[value_col].values[n // 2:].astype(np.float64)

    # --- Labels -----------------------------------------------------------
    labels: Optional[Dict[str, np.ndarray]] = None
    if target_cols is None:
        target_cols = inline_label_cols

    if label_path is not None:
        label_df = pd.read_csv(label_path)
        if key_col in label_df.columns and key_col in per_key.columns:
            label_df = label_df.set_index(key_col).loc[
                per_key[key_col].values
            ].reset_index()
        label_candidates = [c for c in label_df.columns if c != key_col]
        if target_cols:
            label_candidates = [c for c in label_candidates if c in target_cols]
        labels = {c: label_df[c].values for c in label_candidates}
    elif target_cols:
        available = [c for c in target_cols if c in df.columns]
        if available:
            if _is_preaggregated(df, key_col):
                labels = {c: df[c].values for c in available}
            else:
                # Take the label from the first repeat of each key.
                first = df.drop_duplicates(subset=[key_col])
                first = first.set_index(key_col).loc[
                    per_key[key_col].values
                ].reset_index()
                labels = {c: first[c].values for c in available}

    metadata = {
        "source": str(trace_path),
        "label_source": str(label_path) if label_path else None,
        "n_keys": features.shape[0],
        "n_features": features.shape[1],
        "feature_names": FEATURE_NAMES,
        "preaggregated": _is_preaggregated(df, key_col),
    }

    return DataBundle(
        fixed_timings=fixed_timings,
        random_timings=random_timings,
        per_key_features=features,
        per_key_labels=labels,
        metadata=metadata,
    )


# ---------------------------------------------------------------------------
# NPZ loader
# ---------------------------------------------------------------------------

def load_npz(
    npz_path: Union[str, pathlib.Path],
    label_path: Optional[Union[str, pathlib.Path]] = None,
    target_cols: Optional[Sequence[str]] = None,
    key_col: str = "key_id",
) -> DataBundle:
    """Load timing traces from a ``.npz`` archive.

    Expected arrays inside the archive:

    * ``fixed_timings`` — 1-D or 2-D (n_keys, n_repeats)
    * ``random_timings`` — same layout
    * (optional) any additional arrays treated as metadata

    Parameters
    ----------
    npz_path : str or Path
        Path to the ``.npz`` file.
    label_path : str or Path, optional
        CSV with per-key labels.
    target_cols : sequence of str, optional
        Columns to extract from *label_path*.
    key_col : str
        Key column in *label_path*.

    Returns
    -------
    DataBundle
    """
    npz_path = pathlib.Path(npz_path)
    data = np.load(npz_path, allow_pickle=True)

    # Support both naming conventions: "fixed_timings"/"random_timings"
    # and the shorter "fixed"/"random".
    key_fixed = "fixed_timings" if "fixed_timings" in data else "fixed"
    key_random = "random_timings" if "random_timings" in data else "random"
    fixed_raw: np.ndarray = data[key_fixed].astype(np.float64)
    random_raw: np.ndarray = data[key_random].astype(np.float64)

    # Flatten to 1-D for TVLA.
    fixed_flat = fixed_raw.ravel()
    random_flat = random_raw.ravel()

    # --- Per-key features -------------------------------------------------
    def _features_from_2d(arr: np.ndarray) -> np.ndarray:
        """Aggregate each row (key) into 8 summary stats."""
        rows = []
        for row in arr:
            q25, q75 = np.percentile(row, [25, 75])
            rows.append([
                np.min(row),
                np.median(row),
                np.mean(row),
                np.std(row, ddof=1) if len(row) > 1 else 0.0,
                q75 - q25,
                np.percentile(row, 99),
                float(stats.kurtosis(row, fisher=True))
                    if len(row) >= 4 else 0.0,
                float(stats.skew(row)) if len(row) >= 3 else 0.0,
            ])
        return np.array(rows, dtype=np.float64)

    if fixed_raw.ndim == 2:
        features_fixed = _features_from_2d(fixed_raw)
        features_random = _features_from_2d(random_raw)
        features = np.vstack([features_fixed, features_random])
    elif fixed_raw.ndim == 1:
        # Already one value per key — trivial features.
        all_vals = np.concatenate([fixed_raw, random_raw])
        features = all_vals.reshape(-1, 1)
        pad = np.zeros((features.shape[0], len(FEATURE_NAMES) - 1))
        features = np.hstack([features, pad])
    else:
        raise ValueError(
            f"Unexpected fixed_timings shape: {fixed_raw.shape}"
        )

    # --- Labels -----------------------------------------------------------
    labels: Optional[Dict[str, np.ndarray]] = None
    if label_path is not None:
        label_df = pd.read_csv(label_path)
        # Derive common targets if not present
        if "sk_lsb" not in label_df.columns and "sk_byte0" in label_df.columns:
            label_df["sk_lsb"] = label_df["sk_byte0"] % 2
        if "msg_hw_parity" not in label_df.columns and "message_hw" in label_df.columns:
            label_df["msg_hw_parity"] = label_df["message_hw"] % 2

        # If the label CSV has per-key data (with key_id and repeats),
        # aggregate to one row per key and build matching per-key features.
        if key_col in label_df.columns and not _is_preaggregated(label_df, key_col):
            # Build per-key features from the label CSV's timing data
            value_candidates = [c for c in label_df.columns
                                if "timing" in c.lower() or "cycles" in c.lower()
                                or "ticks" in c.lower()]
            if value_candidates:
                per_key_agg = _aggregate_per_key(label_df, key_col, value_candidates[0])
                per_key_agg = per_key_agg.reset_index()
                features = per_key_agg[FEATURE_NAMES].values

            label_df = label_df.drop_duplicates(subset=[key_col]).sort_values(key_col)

        candidates = [c for c in label_df.columns if c != key_col]
        if target_cols:
            candidates = [c for c in candidates if c in target_cols]
        labels = {c: label_df[c].values for c in candidates}

    # --- Metadata ---------------------------------------------------------
    extra_keys = [k for k in data.files
                  if k not in (key_fixed, key_random)]
    extra = {k: data[k] for k in extra_keys}

    metadata = {
        "source": str(npz_path),
        "label_source": str(label_path) if label_path else None,
        "fixed_shape": fixed_raw.shape,
        "random_shape": random_raw.shape,
        "n_keys": features.shape[0],
        "n_features": features.shape[1],
        "feature_names": FEATURE_NAMES,
        **extra,
    }

    return DataBundle(
        fixed_timings=fixed_flat,
        random_timings=random_flat,
        per_key_features=features,
        per_key_labels=labels,
        metadata=metadata,
    )
