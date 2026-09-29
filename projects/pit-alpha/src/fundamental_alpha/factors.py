"""Cross-sectional factor construction and risk neutralization."""

from __future__ import annotations

import numpy as np
import pandas as pd


def robust_winsorize(series: pd.Series, n_mad: float = 5.0) -> pd.Series:
    """Clip outliers around the median using scaled median absolute deviation."""
    values = pd.to_numeric(series, errors="coerce")
    median = values.median()
    mad = (values - median).abs().median()
    if pd.isna(mad) or mad < 1e-12:
        return values.fillna(median)
    scale = 1.4826 * mad
    return values.clip(median - n_mad * scale, median + n_mad * scale).fillna(median)


def zscore(series: pd.Series) -> pd.Series:
    values = pd.to_numeric(series, errors="coerce")
    std = values.std(ddof=0)
    if pd.isna(std) or std < 1e-12:
        return pd.Series(0.0, index=series.index)
    return (values - values.mean()) / std


def _neutralize_one(group: pd.DataFrame, factor: str) -> pd.Series:
    """OLS residual against log market cap and industry dummies."""
    y = group[factor].to_numpy(dtype=float)
    size = np.log(group["market_cap"].clip(lower=1.0)).to_numpy(dtype=float)
    size = (size - size.mean()) / (size.std() if size.std() > 1e-12 else 1.0)
    dummies = pd.get_dummies(group["industry"], drop_first=True, dtype=float)
    columns = [np.ones(len(group)), size]
    if not dummies.empty:
        columns.append(dummies.to_numpy())
    design = np.column_stack(columns)
    residual = y - design @ np.linalg.lstsq(design, y, rcond=None)[0]
    return pd.Series(residual, index=group.index)


def build_factors(aligned: pd.DataFrame) -> pd.DataFrame:
    """Build quality, value, growth and a fixed-weight composite factor."""
    frame = aligned.copy()
    frame["log_pe"] = np.log(frame["pe_ttm"].where(frame["pe_ttm"] > 0))
    frame["log_pb"] = np.log(frame["pb"].where(frame["pb"] > 0))
    components = [
        "roe_ttm",
        "cfo_to_assets",
        "accruals_to_assets",
        "revenue_growth",
        "log_pe",
        "log_pb",
    ]
    for column in components:
        frame[f"z_{column}"] = frame.groupby("date", group_keys=False)[column].transform(
            lambda x: zscore(robust_winsorize(x))
        )

    frame["quality_raw"] = (
        frame["z_roe_ttm"]
        + frame["z_cfo_to_assets"]
        - frame["z_accruals_to_assets"]
    ) / 3.0
    frame["value_raw"] = (-frame["z_log_pe"] - frame["z_log_pb"]) / 2.0
    frame["growth_raw"] = frame["z_revenue_growth"]

    for raw, output in (
        ("quality_raw", "factor_quality"),
        ("value_raw", "factor_value"),
        ("growth_raw", "factor_growth"),
    ):
        residual = frame.groupby("date", group_keys=False).apply(
            lambda group: _neutralize_one(group, raw), include_groups=False
        )
        # groupby.apply creates a date level; restore original row indices.
        if isinstance(residual.index, pd.MultiIndex):
            residual.index = residual.index.get_level_values(-1)
        frame[output] = residual.reindex(frame.index)
        frame[output] = frame.groupby("date", group_keys=False)[output].transform(zscore)

    frame["factor_composite"] = (
        0.50 * frame["factor_quality"]
        + 0.30 * frame["factor_value"]
        + 0.20 * frame["factor_growth"]
    )
    frame["factor_composite"] = frame.groupby("date", group_keys=False)[
        "factor_composite"
    ].transform(zscore)
    return frame.sort_values(["date", "symbol"]).reset_index(drop=True)

