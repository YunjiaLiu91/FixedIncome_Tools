"""Small dependency-free HTML report generator."""

from __future__ import annotations

import html
import json
from pathlib import Path

import pandas as pd


def _fmt(value: object, percent: bool = False) -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return html.escape(str(value))
    if pd.isna(number):
        return "N/A"
    return f"{number:.2%}" if percent else f"{number:.3f}"


def _equity_svg(returns: pd.Series, width: int = 760, height: int = 220) -> str:
    wealth = (1.0 + returns.fillna(0.0)).cumprod()
    if wealth.empty:
        return ""
    low, high = float(wealth.min()), float(wealth.max())
    span = high - low if high > low else 1.0
    coords = []
    for i, value in enumerate(wealth):
        x = 12 + i * (width - 24) / max(len(wealth) - 1, 1)
        y = 12 + (high - float(value)) * (height - 24) / span
        coords.append(f"{x:.1f},{y:.1f}")
    return (
        f'<svg viewBox="0 0 {width} {height}" role="img" aria-label="Long-short equity curve">'
        '<rect width="100%" height="100%" rx="10" fill="#f7faf9"/>'
        f'<polyline fill="none" stroke="#087f5b" stroke-width="3" points="{" ".join(coords)}"/>'
        f'<text x="16" y="28" fill="#47635b" font-size="13">终值 {wealth.iloc[-1]:.2f}</text></svg>'
    )


def write_html_report(
    output_path: Path,
    summary: dict[str, object],
    quantiles: pd.DataFrame,
    decay: pd.DataFrame,
) -> None:
    ic = summary["full_sample_ic"]
    perf = summary["full_sample_performance"]
    oos = summary["out_of_sample_ic"]
    trading = summary["trading"]
    exposure = summary["style_exposure"]
    metric_rows = [
        ("全样本 Rank IC", _fmt(ic["mean_ic"])),
        ("全样本年化 ICIR", _fmt(ic["icir_annualized"])),
        ("样本外 Rank IC", _fmt(oos["mean_ic"])),
        ("多空年化收益", _fmt(perf["annual_return"], True)),
        ("多空 Sharpe", _fmt(perf["sharpe"])),
        ("最大回撤", _fmt(perf["max_drawdown"], True)),
        ("单边月均换手", _fmt(trading["average_one_way_turnover"], True)),
        ("容量代理（亿元）", _fmt(trading["capacity_rmb"] / 1e8)),
    ]
    cards = "".join(
        f'<div class="card"><span>{html.escape(name)}</span><strong>{value}</strong></div>'
        for name, value in metric_rows
    )
    decay_rows = "".join(
        f"<tr><td>{int(row.horizon_months)}</td><td>{row.mean_rank_ic:.3f}</td>"
        f"<td>{int(row.observations)}</td></tr>" for row in decay.itertuples()
    )
    content = f"""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<title>PIT 基本面 Alpha 研究报告</title>
<style>
body{{font-family:system-ui,-apple-system,"Segoe UI",sans-serif;margin:0;background:#eef4f1;color:#18352d}}
main{{max-width:960px;margin:auto;padding:42px 24px}} h1{{font-size:34px;margin-bottom:8px}}
.note{{background:#fff4d6;border-left:5px solid #e9a800;padding:14px 18px;border-radius:8px}}
.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:12px;margin:24px 0}}
.card{{background:white;padding:18px;border-radius:12px;box-shadow:0 2px 12px #173f3312}}
.card span{{display:block;color:#617871;font-size:13px}} .card strong{{font-size:24px}}
section{{background:white;padding:24px;margin:18px 0;border-radius:14px}} table{{width:100%;border-collapse:collapse}}
th,td{{text-align:left;border-bottom:1px solid #e4ece8;padding:10px}} code{{background:#edf3f0;padding:2px 5px}}
</style></head><body><main>
<h1>Point-in-Time 基本面 Alpha</h1>
<p>质量、价值和成长复合因子的可复现研究报告</p>
<div class="note"><strong>数据说明：</strong>本报告使用带已知信号机制的模拟数据，结果用于检查研究流程，不代表真实投资业绩。</div>
<div class="grid">{cards}</div>
<section><h2>多空组合净值（未计成本）</h2>{_equity_svg(quantiles["long_short"])}</section>
<section><h2>信号衰减</h2><table><thead><tr><th>预测期（月）</th><th>平均 Rank IC</th><th>月份数</th></tr></thead>
<tbody>{decay_rows}</tbody></table></section>
<section><h2>中性化检查</h2><p>因子与对数市值的平均月度相关性：<code>{_fmt(exposure["mean_size_correlation"])}</code>；
行业内因子均值绝对值：<code>{_fmt(exposure["mean_abs_industry_score"])}</code>。</p></section>
<section><h2>研究设计</h2><ol><li>信号日只使用公告日不晚于当日的财报。</li>
<li>截面 MAD 去极值并 Z-score 标准化。</li><li>对行业虚拟变量与对数市值做 OLS 中性化。</li>
<li>固定权重合成，按时间切分样本内与样本外。</li><li>用 IC、分层、多空、换手、衰减和容量代理联合诊断。</li></ol></section>
<section><h2>待完善项</h2><p>历史成分股、退市样本、复权、停牌/ST/涨跌停、手续费与冲击成本、财报更正版本、分析师预测快照和风险模型约束。</p></section>
</main></body></html>"""
    output_path.write_text(content, encoding="utf-8")


def write_json(path: Path, payload: dict[str, object]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
