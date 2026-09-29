"""Self-contained report: escaped content, accessible SVGs and local-only controls."""

from __future__ import annotations

import html
import json
from pathlib import Path

import numpy as np


def svg_lines(series: list[tuple[str, list[float], str]], label: str, baseline: float | None = None):
    width, height = 900, 230
    values = [x for _, row, _ in series for x in row]
    if baseline is not None:
        values.append(baseline)
    low, high = min(values), max(values)
    span = max(high - low, 1e-10)
    def y(value):
        return 25 + (high - value) / span * 175
    lines = []
    for title, row, color in series:
        points = " ".join(f"{50 + i * 825 / max(1, len(row) - 1):.1f},{y(v):.1f}" for i, v in enumerate(row))
        lines.append(f'<polyline points="{points}" fill="none" stroke="{color}" stroke-width="1.7"><title>{html.escape(title)}</title></polyline>')
    base = "" if baseline is None else f'<line x1="50" x2="875" y1="{y(baseline):.1f}" y2="{y(baseline):.1f}" stroke="#b2b8c0" stroke-dasharray="4 4"/>'
    return f'<svg viewBox="0 0 {width} {height}" role="img" aria-label="{html.escape(label)}"><text x="2" y="30" font-size="11" fill="#747c86">{high:.3f}</text><text x="2" y="202" font-size="11" fill="#747c86">{low:.3f}</text>{base}{"".join(lines)}<text x="50" y="223" font-size="11" fill="#747c86">窗口起点</text><text x="818" y="223" font-size="11" fill="#747c86">窗口终点</text></svg>'


def fmt(value, unit=""):
    if isinstance(value, bool):
        return str(value).lower()
    if isinstance(value, (int, float)):
        return f"{value:.2%}" if unit == "fraction" else f"{value:,.2f}"
    return html.escape(str(value))


def write_report(path: Path, payload: dict, portfolio, backtest):
    r = payload["risk"]
    counts, sample = payload["counts"], payload["sample"]
    assets = "".join(f'<tr><td>{html.escape(a["symbol"])}</td><td>{html.escape(a["sector"])}</td><td>{a["weight"]:.1%}</td><td>{a["volatility_contribution"]:.2%}</td><td>{a["liquidation_days"]:.2f}</td></tr>' for a in r["assets"])
    checks = "".join(f'<tr data-status="{c["status"]}"><td><span class="tag {c["status"].lower()}">{c["status"]}</span></td><td>{c["rule_id"]} · {html.escape(c["title"])}</td><td>{html.escape(c["entity"])}</td><td>{fmt(c["actual"], c["unit"])}</td><td>{fmt(c["threshold"], c["unit"])}</td><td><details><summary>证据</summary><code>{c["evidence_id"]}</code><p>{html.escape(c["explanation"])}</p></details></td></tr>' for c in payload["checks"])
    orders = "".join(f'<tr><td>{html.escape(d["order_id"])}</td><td>{html.escape(d["symbol"])}</td><td>{d["side"]}</td><td><span class="tag {"fail" if d["status"] == "BLOCK" else "pass"}">{d["status"]}</span></td><td>{", ".join(d["failed_rules"]) or "—"}</td></tr>' for d in payload["order_decisions"])
    scenarios = "".join(f'<tr><td>{html.escape(s["name"])}</td><td>{s["shocks"]["equity_shock"]:.0%}</td><td>{s["shocks"]["yield_bp"]:+} bp</td><td>{s["pnl_cny"]:,.0f}</td><td>{s["return_fraction"]:.2%}</td></tr>' for s in r["scenarios"])
    wealth = np.concatenate(([1.0], np.cumprod(1 + portfolio.to_numpy()))).tolist()
    curve = svg_lines([("模拟固定权重净值", wealth, "#245f84")], "固定当前权重的模拟净值，包含初始净值 1", 1.0)
    bt_chart = svg_lines([("实际损失", backtest.realized_loss.tolist(), "#b3bac4"),
                          ("滚动 VaR", backtest.var_fraction.tolist(), "#245f84")], "实际损失与前 252 日滚动 VaR", 0.0)
    bt = r["backtest"]
    content = '''<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>RiskLens | 风险与交易审查</title><style>
:root{color-scheme:light;--ink:#182632;--muted:#697481;--line:#dce1e7;--blue:#245f84}
*{box-sizing:border-box}body{margin:0;background:#f4f5f7;color:var(--ink);font:14px/1.65 system-ui,"Segoe UI","Microsoft YaHei",sans-serif}
main{max-width:1120px;margin:0 auto;padding:30px 28px 60px}header{border-bottom:2px solid var(--ink);padding-bottom:20px}
.eyebrow{color:var(--blue);font-size:12px;letter-spacing:2px;font-weight:600}h1{font-size:32px;font-weight:600;letter-spacing:-1px;margin:8px 0}
h2{font-size:18px;margin:0 0 14px;font-weight:600}p{margin:8px 0}.muted{color:var(--muted)}.note{padding:12px 16px;margin:18px 0;background:#fff9ec;border:1px solid #e8d8b2}
.metrics{display:grid;grid-template-columns:repeat(4,1fr);gap:1px;background:var(--line);border:1px solid var(--line);margin:20px 0}.metric{background:white;padding:18px}.metric strong{display:block;font-size:27px;font-weight:550;margin:4px 0}.metric small{color:var(--muted)}
section{background:white;border:1px solid var(--line);padding:22px;margin:18px 0}.row{display:grid;grid-template-columns:1fr 1fr;gap:18px}.row section{margin:0}.scroll{overflow:auto}table{border-collapse:collapse;width:100%;font-size:13px}th,td{padding:10px 8px;border-bottom:1px solid var(--line);text-align:left;vertical-align:top}th{font-weight:500;color:var(--muted);white-space:nowrap}svg{width:100%;height:auto;display:block}.tag{font-size:11px;padding:3px 7px;white-space:nowrap}.pass{background:#edf5f1;color:#35614e}.fail{background:#fbefee;color:#933d36}.toolbar{display:flex;justify-content:space-between;align-items:center;gap:12px;margin-bottom:12px}button{background:white;color:var(--ink);border:1px solid #aab5bf;padding:7px 12px;cursor:pointer}button[aria-pressed=true]{background:var(--ink);color:white}details{max-width:240px}summary{cursor:pointer;color:var(--blue)}code{font-size:11px;overflow-wrap:anywhere}label{display:block;margin:12px 0}input[type=range]{width:100%}.stress-value{font-size:28px;font-weight:550;color:var(--blue)}footer{padding-top:20px;color:var(--muted);font-size:12px}.legend{font-size:12px;color:var(--muted)}
@media(max-width:720px){main{padding:20px 14px}.metrics{grid-template-columns:repeat(2,1fr)}.row{grid-template-columns:1fr}h1{font-size:26px}section{padding:16px}}
@media print{body{background:white}main{padding:0}.toolbar,input{display:none}section{break-inside:avoid}.metrics{grid-template-columns:repeat(4,1fr)}}
</style></head><body><main>
<header><div class="eyebrow">RISKLENS / RESEARCH NOTE 01</div><h1>投资组合风险与交易审查</h1><p class="muted">估值日期：@@DATE@@ · CNY · @@ASSETS@@ 类模拟资产 · @@DAYS@@ 个工作日样本</p></header>
<div class="note">本报告基于模拟数据与虚构内部政策。告警供人工复核，不能据此判定违法或监管达标。无真实客户资料，无交易接口。</div>
<div class="metrics"><div class="metric"><small>组合净资产 / CNY</small><strong>@@NAV@@</strong><small>含现金资产</small></div><div class="metric"><small>单日历史 VaR · 97.5%</small><strong>@@VAR@@</strong><small>@@VARP@@ NAV · 最近 252 日</small></div><div class="metric"><small>单日历史 ES · 97.5%</small><strong>@@ES@@</strong><small>@@ESP@@ NAV · 分数尾部加权</small></div><div class="metric"><small>待复核订单</small><strong>@@BLOCKED@@ / @@ORDERS@@</strong><small>@@FAILURES@@ 项检查未通过 / @@CHECKS@@ 项检查</small></div></div>
<div class="row"><section><h2>历史模拟与风险贡献</h2>@@CURVE@@<p class="legend">固定当前权重，每日再平衡的模拟重建路径。非历史实际持仓，非策略业绩。</p><p>近 252 日年化波动：<b>@@VOL@@</b> · 重建路径最大回撤：<b>@@DD@@</b></p></section><section><h2>VaR 滚动回测</h2>@@BACKTEST@@<p class="legend">蓝线：前 252 日 VaR · 灰线：当日损失。预测不使用当日收益。</p><p>@@BTHITS@@ / @@BTN@@ 日损失超过 VaR（@@BTRATE@@，名义目标 2.5%）。Kupiec p 值：@@PVAL@@。</p><p class="muted">覆盖率检验仅检查突破比例，不检验独立性；p 值不能证明模型有效。</p></section></div>
<section><h2>资产暴露与流动性</h2><div class="scroll"><table><thead><tr><th>资产</th><th>行业 / 类别</th><th>权重</th><th>波动贡献</th><th>预计退出天数</th></tr></thead><tbody>@@ASSETROWS@@</tbody></table></div><p class="muted">波动贡献采用协方差 Euler 分解，合计为组合年化波动；退出天数假设每日使用 ADV 的 10%，忽略市场冲击。</p></section>
<div class="row"><section><h2>预设压力场景</h2><div class="scroll"><table><thead><tr><th>场景</th><th>股票</th><th>利率</th><th>损益 / CNY</th><th>占 NAV</th></tr></thead><tbody>@@SCENARIOS@@</tbody></table></div><p class="muted">债券按 −修正久期 × 利率变动估计，忽略凸性与信用利差。场景由研究者设定。</p></section><section><h2>交互压力试算</h2><label for="equity">股票冲击 <output id="equity-label">−20%</output></label><input id="equity" type="range" min="-40" max="10" value="-20"><label for="rates">利率变动 <output id="rates-label">+100 bp</output></label><input id="rates" type="range" min="-100" max="300" step="25" value="100"><label for="gold">黄金冲击 <output id="gold-label">+5%</output></label><input id="gold" type="range" min="-20" max="20" value="5"><div class="stress-value" id="stress-pnl"></div><p class="muted">本地计算；移动滑块仅改变试算，不修改政策和已生成的告警。</p></section></div>
<section><h2>下单前审查结果</h2><div class="scroll"><table><thead><tr><th>订单</th><th>资产</th><th>方向</th><th>演示结论</th><th>未通过规则</th></tr></thead><tbody>@@ORDERROWS@@</tbody></table></div><p class="muted">逐笔独立审查同一持仓快照，尚未实现挂单冻结和批量订单累计检查。PASS_DEMO_CHECKS 仅表示本项目订单规则通过。</p></section>
<section><div class="toolbar"><h2>检查明细与证据</h2><div><button id="all" aria-pressed="false">全部检查</button> <button id="failed" aria-pressed="true">仅未通过</button></div></div><div class="scroll"><table id="checks"><thead><tr><th>状态</th><th>规则</th><th>对象</th><th>实际</th><th>阈值</th><th>说明</th></tr></thead><tbody>@@CHECKROWS@@</tbody></table></div></section>
<section><h2>方法与复现</h2><p>VaR 使用损失样本的经验分布逆函数；ES 精确积分最差 2.5% 的样本质量，边界采用分数权重。当前风险使用最近 252 日；回测逐日滚动相同窗口。</p><p>政策版本：<code>@@POLICY@@</code>。输入 CSV 与政策的 SHA-256 保存在 summary.json，便于定位结果对应的输入。</p><p>AI 协作接口仅生成离线证据包，并校验模型返回的证据编号和数值。自由文本仍需人工语义复核；本次报告没有调用在线模型。</p></section>
<footer>RiskLens v0.1.0 · Python / NumPy / pandas · 固定随机种子 42 · 数值引擎与报告使用同一结果文件</footer>
</main><script>
const assets = @@JSASSETS@@;
function stressUpdate(){const e=Number(document.getElementById('equity').value)/100;const b=Number(document.getElementById('rates').value);const g=Number(document.getElementById('gold').value)/100;document.getElementById('equity-label').textContent=(e*100).toFixed(0)+'%';document.getElementById('rates-label').textContent=(b>=0?'+':'')+b+' bp';document.getElementById('gold-label').textContent=(g>=0?'+':'')+(g*100).toFixed(0)+'%';const pnl=assets.reduce((v,a)=>v+a.market_value*(a.asset_class==='equity'?e:a.asset_class==='bond'?-a.duration*b/10000:a.asset_class==='gold'?g:0),0);document.getElementById('stress-pnl').textContent=pnl.toLocaleString('zh-CN',{maximumFractionDigits:0})+' CNY';}
for(const id of ['equity','rates','gold'])document.getElementById(id).addEventListener('input',stressUpdate);
function filterChecks(failed){for(const row of document.querySelectorAll('#checks tbody tr'))row.hidden=failed&&row.dataset.status!=='FAIL';document.getElementById('all').setAttribute('aria-pressed',String(!failed));document.getElementById('failed').setAttribute('aria-pressed',String(failed));}
document.getElementById('all').addEventListener('click',()=>filterChecks(false));document.getElementById('failed').addEventListener('click',()=>filterChecks(true));stressUpdate();filterChecks(true);
</script></body></html>'''
    replacements = {"DATE": payload["as_of"], "ASSETS": str(sample["assets"]), "DAYS": str(sample["days"]),
                    "NAV": f'{r["nav_cny"]:,.0f}', "VAR": f'{r["var_cny"]:,.0f}', "ES": f'{r["es_cny"]:,.0f}',
                    "VARP": f'{r["var_fraction"]:.2%}', "ESP": f'{r["es_fraction"]:.2%}',
                    "BLOCKED": str(counts["blocked_orders"]), "ORDERS": str(sample["orders"]),
                    "FAILURES": str(counts["failures"]), "CHECKS": str(counts["checks"]),
                    "VOL": f'{r["annualized_volatility"]:.2%}', "DD": f'{r["reconstructed_max_drawdown"]:.2%}',
                    "BTHITS": str(bt["breaches"]), "BTN": str(bt["observations"]), "BTRATE": f'{bt["breach_rate"]:.2%}',
                    "PVAL": f'{bt["kupiec_pvalue"]:.4f}', "ASSETROWS": assets, "SCENARIOS": scenarios,
                    "ORDERROWS": orders, "CHECKROWS": checks, "POLICY": html.escape(payload["policy_version"]),
                    "CURVE": curve, "BACKTEST": bt_chart,
                    "JSASSETS": json.dumps(r["assets"], ensure_ascii=False).replace("<", "\\u003c").replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")}
    content = content.replace("97.5%", f'{r["confidence"]:.1%}').replace("252", str(r["lookback"]))
    content = content.replace("2.5%", f'{1-r["confidence"]:.1%}').replace("10%", f'{payload["policy"]["adv_participation"]:.0%}')
    content = content.replace("固定随机种子 42", f'数据来源：{html.escape(payload["data_source"])} · 随机种子 {payload["seed"]}')
    content = content.replace("本报告基于模拟数据与虚构内部政策", "本报告基于用户提供的数据与虚构内部政策" if payload["data_source"] != "synthetic" else "本报告基于模拟数据与虚构内部政策")
    for key, value in replacements.items():
        content = content.replace("@@" + key + "@@", value)
    path.write_text(content, encoding="utf-8")
