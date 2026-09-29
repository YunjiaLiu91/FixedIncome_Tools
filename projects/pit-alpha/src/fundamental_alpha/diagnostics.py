"""Data-quality diagnostics recorded alongside each experiment."""

from __future__ import annotations

import pandas as pd


FUNDAMENTAL_FEATURES = [
    "roe_ttm",
    "cfo_to_assets",
    "accruals_to_assets",
    "revenue_growth",
    "pe_ttm",
    "pb",
]
MARKET_FEATURES = ["market_cap", "adv20", "forward_return"]


def _missing_rates(frame: pd.DataFrame, columns: list[str]) -> dict[str, float]:
    return {column: float(frame[column].isna().mean()) for column in columns}


def build_data_quality_report(
    fundamentals: pd.DataFrame,
    market: pd.DataFrame,
    aligned: pd.DataFrame,
) -> dict[str, object]:
    """Summarize input integrity and the coverage retained by PIT alignment."""
    report_period = pd.to_datetime(fundamentals["report_period"])
    announce_date = pd.to_datetime(fundamentals["announce_date"])
    cross_section = aligned.groupby("date")["symbol"].nunique()
    age = aligned["statement_age_days"]

    return {
        "fundamentals": {
            "rows": int(len(fundamentals)),
            "stocks": int(fundamentals["symbol"].nunique()),
            "duplicate_versions": int(
                fundamentals.duplicated(
                    ["symbol", "report_period", "announce_date"], keep=False
                ).sum()
            ),
            "announcement_before_report_period": int((announce_date < report_period).sum()),
            "missing_rate": _missing_rates(fundamentals, FUNDAMENTAL_FEATURES),
        },
        "market": {
            "rows": int(len(market)),
            "stocks": int(market["symbol"].nunique()),
            "duplicate_symbol_dates": int(market.duplicated(["symbol", "date"]).sum()),
            "missing_rate": _missing_rates(market, MARKET_FEATURES),
        },
        "pit_alignment": {
            "retained_rows": int(len(aligned)),
            "coverage_rate": float(len(aligned) / len(market)) if len(market) else 0.0,
            "future_announcement_rows": int((aligned["announce_date"] > aligned["date"]).sum()),
            "cross_section_min": int(cross_section.min()),
            "cross_section_median": float(cross_section.median()),
            "cross_section_max": int(cross_section.max()),
            "statement_age_days_median": float(age.median()),
            "statement_age_days_p95": float(age.quantile(0.95)),
        },
    }

