"""Synthetic fixtures and strict input validation; no customer data or market downloads."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd


def generate(seed: int = 42) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range(end="2026-09-28", periods=756)
    common = rng.standard_t(6, len(dates)) * 0.008
    common[-70:-45] -= 0.006  # Explicit simulated stress regime, not a historical event.
    specs = [
        ("SIM_TECH_A", "Technology", "equity", 0.36, 6e6, 0, 4, 1.2),
        ("SIM_TECH_B", "Technology", "equity", 0.20, 4e6, 0, 4, 1.1),
        ("SIM_BANK", "Financials", "equity", 0.14, 18e6, 0, 3, 0.8),
        ("SIM_BOND", "Fixed income", "bond", 0.18, 8e6, 4.5, 2, 0),
        ("SIM_GOLD", "Commodity", "gold", 0.07, 10e6, 0, 3, 0),
        ("CASH", "Cash", "cash", 0.05, 1e12, 0, 1, 0),
    ]
    returns, positions = {}, []
    for symbol, sector, kind, weight, adv, duration, level, beta in specs:
        if kind == "equity":
            series = 0.0002 + beta * common + rng.normal(0, 0.006, len(dates))
        elif kind == "bond":
            series = 0.0001 + rng.normal(0, 0.0018, len(dates))
        elif kind == "gold":
            series = rng.normal(0.0001, 0.009, len(dates)) - common * 0.15
        else:
            series = np.zeros(len(dates))
        returns[symbol] = series
        positions.append(dict(symbol=symbol, sector=sector, asset_class=kind,
                              market_value=10_000_000 * weight, adv_cny=adv,
                              duration=duration, risk_level=level,
                              price_date="2026-09-28"))
    orders = pd.DataFrame([
        ["ORD-001", "SIM_TECH_B", "BUY", 200_000, "2027-09-28", 4],
        ["ORD-002", "SIM_TECH_A", "BUY", 800_000, "2026-08-01", 2],
        ["ORD-003", "SIM_BANK", "SELL", 100_000, "2027-09-28", 4],
        ["ORD-004", "SIM_GOLD", "BUY", 100_000, "2027-09-28", 4],
        ["ORD-005", "SIM_GOLD", "SELL", 900_000, "2027-09-28", 4],
    ], columns=["order_id", "symbol", "side", "notional_cny", "kyc_expiry", "client_risk_level"])
    return pd.DataFrame(returns, index=pd.DatetimeIndex(dates, name="date")), pd.DataFrame(positions), orders


def load_inputs(folder: Path):
    returns = pd.read_csv(folder / "returns.csv", index_col="date", parse_dates=True)
    positions = pd.read_csv(folder / "positions.csv")
    orders = pd.read_csv(folder / "orders.csv")
    return returns, positions, orders


def load_policy(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _require(frame: pd.DataFrame, columns: set[str], label: str):
    missing = columns - set(frame.columns)
    if missing:
        raise ValueError(f"{label}: missing columns {sorted(missing)}")
    if frame.empty or frame[list(columns)].isna().any().any():
        raise ValueError(f"{label}: empty table or missing required values")


def validate(returns: pd.DataFrame, positions: pd.DataFrame, orders: pd.DataFrame, policy: dict):
    _require(positions, {"symbol", "sector", "asset_class", "market_value", "adv_cny",
                         "duration", "risk_level", "price_date"}, "positions")
    _require(orders, {"order_id", "symbol", "side", "notional_cny", "kyc_expiry",
                      "client_risk_level"}, "orders")
    as_of = pd.Timestamp(policy["as_of"])
    if not isinstance(returns.index, pd.DatetimeIndex) or returns.index.hasnans:
        raise ValueError("returns: index must contain valid dates")
    if returns.index.has_duplicates or not returns.index.is_monotonic_increasing:
        raise ValueError("returns: dates must be unique and sorted")
    if returns.columns.has_duplicates or positions.symbol.duplicated().any():
        raise ValueError("duplicate asset symbols")
    if orders.order_id.duplicated().any():
        raise ValueError("duplicate order IDs")
    if set(returns.columns) != set(positions.symbol):
        raise ValueError("returns columns must match positions exactly")
    values = returns.to_numpy(dtype=float)
    if not np.isfinite(values).all() or (values <= -1).any():
        raise ValueError("returns: NaN, infinite or returns <= -100%")
    if len(returns) <= policy["lookback"] or returns.index.max() > as_of:
        raise ValueError("returns: insufficient history or future observations")
    if returns.index.max().normalize() != as_of.normalize():
        raise ValueError("returns must end on policy as_of date")
    numeric = positions[["market_value", "adv_cny", "duration", "risk_level"]].to_numpy(dtype=float)
    if not np.isfinite(numeric).all() or (numeric < 0).any():
        raise ValueError("positions: invalid numeric inputs")
    if positions.market_value.sum() <= 0 or (positions.adv_cny <= 0).any():
        raise ValueError("positions: NAV and ADV must be positive")
    if not positions.asset_class.isin(["equity", "bond", "gold", "cash"]).all():
        raise ValueError("unsupported asset class")
    if (positions.asset_class == "cash").sum() != 1:
        raise ValueError("exactly one cash asset is required")
    price_dates = pd.to_datetime(positions.price_date, errors="raise")
    if price_dates.isna().any() or (price_dates > as_of).any():
        raise ValueError("positions: invalid/future price dates")
    if not orders.symbol.isin(positions.loc[positions.asset_class != "cash", "symbol"]).all():
        raise ValueError("orders must use known non-cash assets")
    if not orders.side.isin(["BUY", "SELL"]).all():
        raise ValueError("orders: side must be BUY or SELL")
    ov = orders[["notional_cny", "client_risk_level"]].to_numpy(dtype=float)
    if not np.isfinite(ov).all() or (orders.notional_cny <= 0).any():
        raise ValueError("orders: invalid numeric inputs")
    if pd.to_datetime(orders.kyc_expiry, errors="raise").isna().any():
        raise ValueError("orders: invalid KYC expiry")
    for levels in [positions.risk_level, orders.client_risk_level]:
        if not levels.isin([1, 2, 3, 4, 5]).all():
            raise ValueError("risk levels must be integer values from 1 to 5")
    if not 0 < policy["confidence"] < 1 or not isinstance(policy["lookback"], int) or policy["lookback"] < 2:
        raise ValueError("invalid confidence or lookback")
    for key in ["max_asset_weight", "max_sector_weight", "max_var_fraction", "adv_participation", "max_order_adv_fraction"]:
        if not 0 < policy[key] <= 1:
            raise ValueError(f"invalid policy threshold: {key}")
    if policy["max_price_age_days"] < 0 or policy["max_liquidation_days"] <= 0:
        raise ValueError("invalid policy age/liquidity limit")
    for shock in policy["scenarios"].values():
        if not all(np.isfinite(float(shock[k])) for k in ["equity_shock", "yield_bp", "gold_shock"]):
            raise ValueError("invalid stress shock")
