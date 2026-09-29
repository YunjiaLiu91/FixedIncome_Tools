"""Deterministic synthetic data for exercising the research pipeline.

The generator deliberately embeds a small relationship between slow-moving
fundamentals and future returns. It validates research code; it is not evidence
that the factor works in real markets.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


INDUSTRIES = ("消费", "医药", "科技", "工业", "金融", "材料")


def _standardize(values: np.ndarray) -> np.ndarray:
    std = values.std()
    return (values - values.mean()) / (std if std > 1e-12 else 1.0)


def generate_demo_data(
    n_stocks: int = 180,
    start: str = "2016-01-31",
    end: str = "2025-12-31",
    seed: int = 42,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return ``(fundamentals, market)`` with realistic PIT date columns."""
    rng = np.random.default_rng(seed)
    symbols = np.array([f"S{i:04d}" for i in range(n_stocks)])
    industry = rng.choice(INDUSTRIES, size=n_stocks)
    base_log_cap = rng.normal(22.2, 0.9, n_stocks)

    quarter_ends = pd.date_range(pd.Timestamp(start) - pd.offsets.QuarterEnd(2), end, freq="QE")
    q_state = rng.normal(0, 1, n_stocks)
    v_state = rng.normal(0, 1, n_stocks)
    g_state = rng.normal(0, 1, n_stocks)
    fundamental_rows: list[dict[str, object]] = []
    latent_by_quarter: dict[pd.Timestamp, tuple[np.ndarray, np.ndarray, np.ndarray]] = {}

    for report_period in quarter_ends:
        q_state = 0.82 * q_state + rng.normal(0, 0.55, n_stocks)
        v_state = 0.72 * v_state + rng.normal(0, 0.70, n_stocks)
        g_state = 0.75 * g_state + rng.normal(0, 0.65, n_stocks)
        latent_by_quarter[report_period] = (q_state.copy(), v_state.copy(), g_state.copy())
        lags = rng.integers(28, 76, n_stocks)
        for i, symbol in enumerate(symbols):
            assets = np.exp(base_log_cap[i]) * rng.uniform(0.45, 1.3)
            roe = 0.105 + 0.035 * q_state[i] + rng.normal(0, 0.012)
            cfo_to_assets = 0.060 + 0.025 * q_state[i] + rng.normal(0, 0.012)
            accruals = 0.018 - 0.020 * q_state[i] + rng.normal(0, 0.010)
            revenue_growth = 0.10 + 0.075 * g_state[i] + rng.normal(0, 0.025)
            pe = np.clip(np.exp(3.05 - 0.28 * v_state[i] + rng.normal(0, 0.13)), 4, 120)
            pb = np.clip(np.exp(1.20 - 0.22 * v_state[i] + rng.normal(0, 0.11)), 0.4, 18)
            fundamental_rows.append(
                {
                    "symbol": symbol,
                    "industry": industry[i],
                    "report_period": report_period,
                    "announce_date": report_period + pd.Timedelta(days=int(lags[i])),
                    "total_assets": assets,
                    "roe_ttm": roe,
                    "cfo_to_assets": cfo_to_assets,
                    "accruals_to_assets": accruals,
                    "revenue_growth": revenue_growth,
                    "pe_ttm": pe,
                    "pb": pb,
                }
            )

    fundamentals = pd.DataFrame(fundamental_rows)
    months = pd.date_range(start, end, freq="ME")
    market_rows: list[dict[str, object]] = []
    evolving_log_cap = base_log_cap.copy()

    sorted_quarters = sorted(latent_by_quarter)
    for date in months:
        # Returns depend on the latest report whose typical announcement lag has passed.
        eligible = [q for q in sorted_quarters if q + pd.Timedelta(days=76) <= date]
        source_q = eligible[-1] if eligible else sorted_quarters[0]
        quality, value, growth = latent_by_quarter[source_q]
        common_market = rng.normal(0.006, 0.035)
        industry_shock = {name: rng.normal(0, 0.018) for name in INDUSTRIES}
        expected = 0.0045 * _standardize(quality) + 0.0028 * _standardize(value)
        expected += 0.0018 * _standardize(growth)
        returns = common_market + expected + np.array([industry_shock[x] for x in industry])
        returns += rng.normal(0, 0.070, n_stocks)
        adv20 = np.exp(evolving_log_cap) * rng.uniform(0.004, 0.025, n_stocks)
        for i, symbol in enumerate(symbols):
            market_rows.append(
                {
                    "date": date,
                    "symbol": symbol,
                    "industry": industry[i],
                    "market_cap": float(np.exp(evolving_log_cap[i])),
                    "adv20": float(adv20[i]),
                    "forward_return": float(returns[i]),
                }
            )
        # The return is earned *after* this signal-date snapshot, so it only
        # changes the market capitalization observed at the following month end.
        evolving_log_cap = evolving_log_cap + np.log1p(np.clip(returns, -0.8, None))

    return fundamentals, pd.DataFrame(market_rows)

