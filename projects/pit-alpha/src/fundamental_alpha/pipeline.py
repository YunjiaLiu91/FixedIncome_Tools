"""End-to-end experiment orchestration."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from .diagnostics import build_data_quality_report
from .evaluation import (
    decay_analysis,
    ic_summary,
    monthly_rank_ic,
    performance_summary,
    portfolio_weights,
    quantile_returns,
    style_exposure,
    turnover_and_capacity,
)
from .factors import build_factors
from .point_in_time import align_fundamentals_asof
from .report import write_html_report, write_json
from .synthetic import generate_demo_data


def run_demo(output_dir: str | Path, seed: int = 42, split_date: str = "2022-01-01") -> dict:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    fundamentals, market = generate_demo_data(seed=seed)
    aligned = align_fundamentals_asof(market, fundamentals)
    panel = build_factors(aligned)
    factor = "factor_composite"

    ic = monthly_rank_ic(panel, factor)
    quantiles = quantile_returns(panel, factor)
    decay = decay_analysis(panel, factor)
    weights = portfolio_weights(panel, factor)
    split = pd.Timestamp(split_date)
    in_sample = panel[panel["date"] < split]
    out_sample = panel[panel["date"] >= split]

    summary = {
        "data_note": "当前结果基于模拟数据，用于验证研究流程，不代表真实投资表现。",
        "seed": seed,
        "split_date": str(split.date()),
        "observations": int(len(panel)),
        "stocks": int(panel["symbol"].nunique()),
        "months": int(panel["date"].nunique()),
        "full_sample_ic": ic_summary(ic),
        "in_sample_ic": ic_summary(monthly_rank_ic(in_sample, factor)),
        "out_of_sample_ic": ic_summary(monthly_rank_ic(out_sample, factor)),
        "full_sample_performance": performance_summary(quantiles["long_short"]),
        "trading": turnover_and_capacity(weights),
        "style_exposure": style_exposure(panel, factor),
    }
    data_quality = build_data_quality_report(fundamentals, market, aligned)
    experiment_manifest = {
        "experiment_id": "demo_quality_value_growth_v1",
        "data": {
            "source": "synthetic",
            "seed": seed,
            "frequency": "monthly",
            "return_column": "forward_return",
        },
        "point_in_time_rule": "announce_date <= signal_date; keep latest visible statement",
        "factor_definition": {
            "quality": "mean(z(roe_ttm), z(cfo_to_assets), -z(accruals_to_assets))",
            "value": "mean(-z(log(pe_ttm)), -z(log(pb)))",
            "growth": "z(revenue_growth)",
            "composite": "0.50 * quality + 0.30 * value + 0.20 * growth",
        },
        "preprocessing": [
            "cross-sectional 5-MAD winsorization",
            "cross-sectional z-score",
            "OLS neutralization against industry dummies and log market cap",
        ],
        "validation": {
            "split_date": str(split.date()),
            "quantiles": 5,
            "decay_horizons_months": [1, 3, 6],
            "capacity_participation_rate": 0.10,
        },
    }

    panel.to_csv(output / "aligned_panel.csv", index=False, encoding="utf-8-sig")
    ic.to_csv(output / "monthly_ic.csv", index=False, encoding="utf-8-sig")
    quantiles.to_csv(output / "quantile_returns.csv", index=False, encoding="utf-8-sig")
    decay.to_csv(output / "decay.csv", index=False, encoding="utf-8-sig")
    write_json(output / "summary.json", summary)
    write_json(output / "data_quality.json", data_quality)
    write_json(output / "experiment_manifest.json", experiment_manifest)
    write_html_report(output / "report.html", summary, quantiles, decay)
    return summary
