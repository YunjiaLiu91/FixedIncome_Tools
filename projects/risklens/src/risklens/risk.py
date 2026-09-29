"""Historical risk measures with explicit finite-sample conventions."""

from __future__ import annotations

import math

import numpy as np
import pandas as pd


def historical_tail(returns, confidence: float = 0.975) -> tuple[float, float]:
    """Loss VaR = inverse empirical CDF; ES integrates exactly the worst (1-q) mass.

    Fractional weight at the tail boundary avoids biased tie/quantile selection.
    Report downside risk floored at zero. No normality or horizon scaling.
    """
    r = np.asarray(returns, dtype=float)
    if r.ndim != 1 or not len(r) or not np.isfinite(r).all() or not 0 < confidence < 1:
        raise ValueError("finite 1D returns and confidence in (0, 1) required")
    losses = np.sort(-r)
    var = losses[max(0, math.ceil(confidence * len(r)) - 1)]
    tail = (1 - confidence) * len(r)
    count = min(int(math.floor(tail)), len(r))
    fraction = tail - count
    total = float(losses[-count:].sum()) if count else 0.0
    if fraction > 0 and count < len(r):
        total += fraction * losses[-count - 1]
    return max(0.0, float(var)), max(0.0, total / tail)


def max_drawdown(returns) -> float:
    wealth = np.concatenate(([1.0], np.cumprod(1 + np.asarray(returns))))
    return float(np.min(wealth / np.maximum.accumulate(wealth) - 1))


def rolling_var_backtest(returns: pd.Series, window: int, confidence: float) -> pd.DataFrame:
    records = []
    for i in range(window, len(returns)):
        var, _ = historical_tail(returns.iloc[i - window:i], confidence)
        loss = -float(returns.iloc[i])
        records.append(dict(date=str(returns.index[i].date()), var_fraction=var,
                            realized_loss=loss, breach=bool(loss > var)))
    return pd.DataFrame(records)


def coverage_test(breaches, confidence: float) -> dict:
    hits = np.asarray(breaches, dtype=bool)
    n, x = len(hits), int(hits.sum())
    if not n:
        raise ValueError("backtest requires observations")
    p = 1 - confidence
    log_null = x * math.log(p) + (n - x) * math.log1p(-p)
    log_fit = 0.0
    if x:
        log_fit += x * math.log(x / n)
    if x < n:
        log_fit += (n - x) * math.log1p(-x / n)
    lr = max(0.0, 2 * (log_fit - log_null))
    return dict(observations=n, breaches=x, breach_rate=x / n, expected_rate=p,
                kupiec_lr=lr, kupiec_pvalue=math.erfc(math.sqrt(lr / 2)),
                note="Asymptotic chi-square(1) coverage test; does not test independence or validate the model")


def stress(positions: pd.DataFrame, scenarios: dict) -> list[dict]:
    nav = float(positions.market_value.sum())
    results = []
    for name, shocks in scenarios.items():
        items = []
        for p in positions.itertuples():
            change = {"equity": shocks["equity_shock"], "bond": -p.duration * shocks["yield_bp"] / 10_000,
                      "gold": shocks["gold_shock"], "cash": 0.0}[p.asset_class]
            items.append(dict(symbol=p.symbol, return_fraction=float(change), pnl_cny=float(p.market_value * change)))
        pnl = sum(i["pnl_cny"] for i in items)
        results.append(dict(name=name, pnl_cny=pnl, return_fraction=pnl / nav, details=items, shocks=shocks))
    return results


def analyse(returns: pd.DataFrame, positions: pd.DataFrame, policy: dict) -> tuple[dict, pd.DataFrame, pd.Series]:
    p = positions.set_index("symbol").loc[returns.columns].rename_axis("symbol")
    nav = float(p.market_value.sum())
    w = p.market_value.to_numpy() / nav
    portfolio = pd.Series(returns.to_numpy() @ w, index=returns.index, name="portfolio_return")
    window = policy["lookback"]
    var, es = historical_tail(portfolio.iloc[-window:], policy["confidence"])
    covariance = returns.iloc[-window:].cov().to_numpy() * 252
    vol = float(np.sqrt(max(0.0, w @ covariance @ w)))
    contribution = w * (covariance @ w) / vol if vol > 0 else np.zeros_like(w)
    bt = rolling_var_backtest(portfolio, window, policy["confidence"])
    assets = [dict(symbol=row.symbol, sector=row.sector, asset_class=row.asset_class,
                   market_value=float(row.market_value), weight=float(row.market_value / nav), duration=float(row.duration),
                   volatility_contribution=float(contribution[i]),
                   liquidation_days=0.0 if row.asset_class == "cash" else float(row.market_value / (row.adv_cny * policy["adv_participation"])))
              for i, row in enumerate(p.reset_index().itertuples())]
    summary = dict(nav_cny=nav, confidence=policy["confidence"], lookback=window,
                   var_fraction=var, es_fraction=es, var_cny=var * nav, es_cny=es * nav,
                   annualized_volatility=vol, reconstructed_max_drawdown=max_drawdown(portfolio),
                   backtest=coverage_test(bt.breach, policy["confidence"]), assets=assets,
                   scenarios=stress(positions, policy["scenarios"]),
                   return_basis="Fixed current weights rebalanced daily on simulated returns; not historical holdings or strategy performance")
    return summary, bt, portfolio
