"""Point-in-time alignment of accounting data to signal dates."""

from __future__ import annotations

import pandas as pd


REQUIRED_FUNDAMENTAL_COLUMNS = {
    "symbol",
    "report_period",
    "announce_date",
    "roe_ttm",
    "cfo_to_assets",
    "accruals_to_assets",
    "revenue_growth",
    "pe_ttm",
    "pb",
}
REQUIRED_MARKET_COLUMNS = {
    "date",
    "symbol",
    "industry",
    "market_cap",
    "adv20",
    "forward_return",
}


def _require_columns(frame: pd.DataFrame, required: set[str], name: str) -> None:
    missing = required.difference(frame.columns)
    if missing:
        raise ValueError(f"{name} missing columns: {sorted(missing)}")


def validate_fundamentals(fundamentals: pd.DataFrame) -> pd.DataFrame:
    """Validate dates and collapse duplicate announcement versions deterministically."""
    _require_columns(fundamentals, REQUIRED_FUNDAMENTAL_COLUMNS, "fundamentals")
    frame = fundamentals.copy()
    frame["report_period"] = pd.to_datetime(frame["report_period"])
    frame["announce_date"] = pd.to_datetime(frame["announce_date"])
    invalid = frame["announce_date"] < frame["report_period"]
    if invalid.any():
        raise ValueError("announce_date earlier than report_period")
    # If a vendor supplies multiple rows for one report, the last row available that
    # day wins. Production systems should keep an explicit revision/version field.
    frame = frame.sort_values(["symbol", "announce_date", "report_period"])
    return frame.drop_duplicates(["symbol", "announce_date"], keep="last")


def align_fundamentals_asof(
    market: pd.DataFrame,
    fundamentals: pd.DataFrame,
    max_age_days: int = 550,
) -> pd.DataFrame:
    """Attach the latest *announced* statement visible on every signal date.

    The implementation groups by symbol to make the sort contract explicit and
    easy to audit. Rows without a known, sufficiently recent statement are dropped.
    """
    _require_columns(market, REQUIRED_MARKET_COLUMNS, "market")
    right = validate_fundamentals(fundamentals)
    left = market.copy()
    left["date"] = pd.to_datetime(left["date"])

    fundamental_payload = [
        col for col in right.columns if col not in {"symbol", "industry", "announce_date"}
    ]
    aligned_parts: list[pd.DataFrame] = []
    right_groups = {key: value for key, value in right.groupby("symbol", sort=False)}
    for symbol, market_part in left.groupby("symbol", sort=False):
        statement_part = right_groups.get(symbol)
        if statement_part is None:
            continue
        lhs = market_part.sort_values("date")
        rhs = statement_part[["announce_date", *fundamental_payload]].sort_values(
            "announce_date"
        )
        joined = pd.merge_asof(
            lhs,
            rhs,
            left_on="date",
            right_on="announce_date",
            direction="backward",
            allow_exact_matches=True,
        )
        aligned_parts.append(joined)

    if not aligned_parts:
        return left.iloc[0:0].copy()
    aligned = pd.concat(aligned_parts, ignore_index=True)
    aligned = aligned.dropna(subset=["announce_date", "report_period"])
    aligned["statement_age_days"] = (
        aligned["date"] - aligned["report_period"]
    ).dt.days
    aligned = aligned[aligned["statement_age_days"] <= max_age_days].copy()
    if (aligned["announce_date"] > aligned["date"]).any():
        raise AssertionError("future information detected after PIT alignment")
    return aligned.sort_values(["date", "symbol"]).reset_index(drop=True)
