"""Evaluation metrics for cross-sectional equity factors."""

from __future__ import annotations

import math

import numpy as np
import pandas as pd


def monthly_rank_ic(panel: pd.DataFrame, factor: str) -> pd.DataFrame:
    rows = []
    for date, group in panel.groupby("date", sort=True):
        valid = group[[factor, "forward_return"]].dropna()
        ic = valid[factor].rank().corr(valid["forward_return"].rank())
        rows.append({"date": date, "ic": ic, "n": len(valid)})
    return pd.DataFrame(rows)


def ic_summary(ic: pd.DataFrame) -> dict[str, float]:
    values = ic["ic"].dropna()
    mean = float(values.mean()) if len(values) else float("nan")
    std = float(values.std(ddof=1)) if len(values) > 1 else float("nan")
    return {
        "mean_ic": mean,
        "ic_std": std,
        "icir_annualized": mean / std * math.sqrt(12) if std > 0 else float("nan"),
        "ic_t_stat": mean / (std / math.sqrt(len(values))) if std > 0 else float("nan"),
        "ic_positive_rate": float((values > 0).mean()) if len(values) else float("nan"),
        "months": int(len(values)),
    }


def quantile_returns(
    panel: pd.DataFrame, factor: str, n_quantiles: int = 5
) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for date, group in panel.groupby("date", sort=True):
        valid = group[[factor, "forward_return"]].dropna().copy()
        if len(valid) < n_quantiles * 2:
            continue
        valid["quantile"] = pd.qcut(
            valid[factor].rank(method="first"), n_quantiles, labels=False
        ) + 1
        means = valid.groupby("quantile")["forward_return"].mean()
        row: dict[str, object] = {"date": date}
        for q in range(1, n_quantiles + 1):
            row[f"Q{q}"] = float(means.get(q, np.nan))
        row["quantile_spread"] = row[f"Q{n_quantiles}"] - row["Q1"]
        # Match portfolio_weights: 50% long, 50% short, gross exposure = 100%.
        row["long_short"] = 0.5 * row["quantile_spread"]
        rows.append(row)
    return pd.DataFrame(rows)


def performance_summary(returns: pd.Series, periods_per_year: int = 12) -> dict[str, float]:
    clean = returns.dropna().astype(float)
    if clean.empty:
        return {key: float("nan") for key in ("annual_return", "annual_vol", "sharpe", "max_drawdown")}
    annual_return = float(clean.mean() * periods_per_year)
    annual_vol = float(clean.std(ddof=1) * math.sqrt(periods_per_year))
    wealth = (1.0 + clean).cumprod()
    # Include the initial NAV of 1 when measuring the first period's loss.
    drawdown = wealth / wealth.cummax().clip(lower=1.0) - 1.0
    return {
        "annual_return": annual_return,
        "annual_vol": annual_vol,
        "sharpe": annual_return / annual_vol if annual_vol > 0 else float("nan"),
        "max_drawdown": float(drawdown.min()),
    }


def portfolio_weights(panel: pd.DataFrame, factor: str, n_quantiles: int = 5) -> pd.DataFrame:
    rows: list[pd.DataFrame] = []
    for date, group in panel.groupby("date", sort=True):
        valid = group[["symbol", factor, "adv20"]].dropna().copy()
        if len(valid) < n_quantiles * 2:
            continue
        valid["bucket"] = pd.qcut(
            valid[factor].rank(method="first"), n_quantiles, labels=False
        ) + 1
        valid["weight"] = 0.0
        top = valid["bucket"] == n_quantiles
        bottom = valid["bucket"] == 1
        valid.loc[top, "weight"] = 0.5 / top.sum()
        valid.loc[bottom, "weight"] = -0.5 / bottom.sum()
        valid["date"] = date
        rows.append(valid[["date", "symbol", "weight", "adv20"]])
    return pd.concat(rows, ignore_index=True) if rows else pd.DataFrame()


def turnover_and_capacity(weights: pd.DataFrame, participation_rate: float = 0.10) -> dict[str, float]:
    if weights.empty:
        return {"average_one_way_turnover": float("nan"), "capacity_rmb": float("nan")}
    wide = weights.pivot(index="date", columns="symbol", values="weight").fillna(0.0)
    trades = wide.diff().fillna(wide)
    one_way = 0.5 * trades.abs().sum(axis=1)
    adv = weights.pivot(index="date", columns="symbol", values="adv20").reindex_like(wide)
    capacities = []
    for date in trades.index:
        delta = trades.loc[date].abs()
        binding = delta > 1e-12
        if binding.any():
            capacities.append(float((participation_rate * adv.loc[date, binding] / delta[binding]).min()))
    return {
        "average_one_way_turnover": float(one_way.iloc[1:].mean()),
        "capacity_rmb": float(np.median(capacities[1:])) if len(capacities) > 1 else float("nan"),
    }


def decay_analysis(panel: pd.DataFrame, factor: str, horizons: tuple[int, ...] = (1, 3, 6)) -> pd.DataFrame:
    frame = panel.sort_values(["symbol", "date"]).copy()
    rows = []
    for horizon in horizons:
        future = pd.Series(index=frame.index, dtype=float)
        for _, group in frame.groupby("symbol", sort=False):
            values = group["forward_return"].to_numpy(dtype=float)
            compounded = np.full(len(values), np.nan)
            for i in range(len(values) - horizon + 1):
                compounded[i] = np.prod(1.0 + values[i : i + horizon]) - 1.0
            future.loc[group.index] = compounded
        temp = frame.assign(_future=future)
        monthly = temp.groupby("date").apply(
            lambda g: g[factor].rank().corr(g["_future"].rank()),
            include_groups=False,
        )
        rows.append(
            {
                "horizon_months": horizon,
                "mean_rank_ic": float(monthly.mean()),
                "observations": int(monthly.notna().sum()),
            }
        )
    return pd.DataFrame(rows)


def style_exposure(panel: pd.DataFrame, factor: str) -> dict[str, float]:
    monthly_size_corr = panel.groupby("date").apply(
        lambda g: g[factor].corr(np.log(g["market_cap"].clip(lower=1.0))),
        include_groups=False,
    )
    industry_means = panel.groupby(["date", "industry"])[factor].mean().abs()
    return {
        "mean_size_correlation": float(monthly_size_corr.mean()),
        "mean_abs_industry_score": float(industry_means.mean()),
    }
