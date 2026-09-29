"""A plain operations brief with evidence links and local CSV exports."""

from html import escape


def table(rows, columns):
    header = "".join(f"<th>{escape(label)}</th>" for _, label in columns)
    cells = []
    for row in rows:
        cells.append("<tr>" + "".join(f"<td>{escape(str(row.get(key, '')))}</td>" for key, _ in columns) + "</tr>")
    return f"<div class='scroll'><table><thead><tr>{header}</tr></thead><tbody>{''.join(cells)}</tbody></table></div>"


def market_rows(snapshots):
    result = []
    for q in snapshots:
        unit = "收益率 %" if q["asset_class"] == "bond" else "元" if q["asset_class"] == "equity" else "点"
        result.append(dict(name=q["name"], instrument=q["instrument_id"], date=q["asof_date"], vendor=q["vendor"],
                           mid=f"{q['mid'] * (100 if q['asset_class'] == 'bond' else 1):.4f}", unit=unit,
                           status="当天" if q["age_days"] == 0 else f"缺当天 / {q['age_days']}日"))
    return result


def brief_text(result):
    counts = result["counts"]
    lines = ["# 市场数据核对简报", "", f"行情截止：{result['settings']['cutoff']}。数据为模拟样例。", "",
             f"共接收 {result['raw_rows']} 行：保留 {counts['accepted']} 行，隔离 {counts['rejected']} 行，"
             f"截止时点后 {counts['not_available']} 行，修订或重传 {counts['superseded']} 行。", "",
             "## 当日需复核", ""]
    lines += [f"- {f['instrument_id']}：{f['detail']}（{f['code']}）。" for f in result["findings"]]
    lines += ["", "## 样例期间变化", "", "以同一数据源的首尾有效记录计算，未对缺失值补齐。", ""]
    for m in result["movements"]:
        lines.append(f"- {m['name']}：{m['start_date']} 至 {m['end_date']}，{m['change']:+.2f}{m['unit']}，来源 {m['vendor']}。")
    lines += ["", "## 需求反馈", "",
              f"{result['feedback_rows']} 条模拟反馈合并为 {len(result['queue'])} 个问题；按影响和紧急程度的显式规则排序。", ""]
    lines += [f"- {q['priority']} / {q['ticket_id']}：{q['title']}。验收：{q['acceptance']}。" for q in result["queue"]]
    lines += ["", "## 资料更新", "", "产品资料查阅日期与行情截止日期分开记录；以下是公开产品说明的整理，不是新闻速报或实测评测。", ""]
    lines += [f"- {s['product']}（{s['observed_on']}）：{s['observation']} [{s['entry_id']}]({s['url']})。" for s in result["sources"]]
    return "\n".join(lines) + "\n"


def html_report(result):
    settings, counts = result["settings"], result["counts"]
    meta = escape(settings["cutoff"])
    market = table(market_rows(result["snapshots"]), [("name", "标的"), ("date", "行情日期"), ("vendor", "来源"),
                                                     ("mid", "中间值"), ("unit", "单位"), ("status", "覆盖")])
    findings = "".join(f"<li><strong>{escape(f['instrument_id'])}</strong> · {escape(f['detail'])}</li>" for f in result["findings"])
    bonds = []
    for b in result["bonds"]:
        bonds.append(dict(symbol=b["instrument_id"], clean=f"{b['clean_price']:.6f}", dirty=f"{b['dirty_price']:.6f}",
                          accrued=f"{b['accrued_interest']:.6f}", dv01=f"{b['dv01_per_100']:.6f}",
                          diff=f"{b['pv_difference']:.2e}"))
    bond_table = table(bonds, [("symbol", "标的"), ("clean", "净价"), ("accrued", "应计利息"), ("dirty", "全价"),
                              ("dv01", "DV01 / 100面值"), ("diff", "现金流复核差")])
    exceptions = [dict(d) for d in result["decisions"] if d["disposition"] != "accepted"]
    for d in exceptions:
        d["display_status"] = {"rejected": "隔离", "not_available": "截止后", "superseded": "修订/重传"}[d["disposition"]]
    exception_table = table(exceptions, [("source_line", "原始行"), ("record_id", "记录编号"), ("instrument_id", "标的"),
                                         ("display_status", "处理"), ("reason", "原因")])
    queue = table(result["queue"], [("ticket_id", "编号"), ("priority", "优先级"), ("title", "需求"),
                                    ("reports", "反馈数"), ("acceptance", "验收条件")])
    sources = "".join(f"<tr><td><a href='{escape(s['url'], quote=True)}'>{escape(s['product'])}</a></td>"
                      f"<td>{escape(s['observation'])}</td><td>{escape(s['follow_up'])}</td></tr>" for s in result["sources"])
    return f"""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>市场数据核对简报</title><style>
*{{box-sizing:border-box}}body{{margin:0;background:#f4f5f6;color:#20272f;font:14px/1.65 Arial,'Microsoft YaHei',sans-serif}}
main{{max-width:1120px;margin:32px auto;background:white;padding:36px 42px;border:1px solid #dce1e5}}
header{{border-bottom:2px solid #213a50;padding-bottom:20px}}.eyebrow{{font-size:12px;color:#566474;letter-spacing:1px}}
h1{{font-size:27px;margin:6px 0}}h2{{font-size:18px;margin:30px 0 12px}}p{{margin:8px 0}}.muted{{color:#687581;font-size:12px}}
.summary{{display:flex;gap:32px;flex-wrap:wrap;padding:17px 0;border-bottom:1px solid #dde2e6}}
.summary strong{{display:block;font-size:22px;font-weight:500}}.summary span{{color:#607080;font-size:12px}}
table{{width:100%;border-collapse:collapse;font-size:12px}}th{{text-align:left;background:#eef1f4;color:#314455;font-weight:600}}
th,td{{padding:10px 12px;border-bottom:1px solid #e3e7ea;vertical-align:top}}td{{font-variant-numeric:tabular-nums}}
.scroll{{overflow-x:auto}}ul{{padding-left:21px}}a{{color:#24557b;text-decoration:none}}a:hover{{text-decoration:underline}}
.notice{{border-left:3px solid #ba893f;padding:9px 14px;background:#faf7f0}}footer{{margin-top:30px;padding-top:16px;border-top:1px solid #ddd}}
@media(max-width:700px){{main{{margin:0;padding:22px 16px}}h1{{font-size:23px}}.summary{{gap:20px}}}}
@media print{{body{{background:white}}main{{border:0;margin:0;padding:0}}a{{color:inherit}}}}
</style></head><body><main>
<header><div class="eyebrow">金融投资运营 · 样例工作记录</div><h1>市场数据核对简报</h1>
<p>行情截止 {meta} · 六个虚构标的 · 两路模拟数据源</p>
<p class="muted">公开产品资料另于 {escape(settings['source_review_date'])} 查阅；不计入行情时点。政策 {escape(settings['policy_version'])}。</p></header>
<div class="summary"><div><strong>{result['raw_rows']}</strong><span>原始行</span></div><div><strong>{counts['accepted']}</strong><span>保留</span></div>
<div><strong>{counts['rejected']}</strong><span>隔离</span></div><div><strong>{counts['not_available']}</strong><span>截止后</span></div>
<div><strong>{counts['superseded']}</strong><span>修订 / 重传</span></div><div><strong>{len(result['queue'])}</strong><span>需求组</span></div></div>
<h2>1. 行情核对</h2><div class="notice"><ul>{findings}</ul></div><p class="muted">优先使用 feed_a；仅比较同一天的两路行情。债券是收益率双边报价，不是债券净价买卖盘。</p>{market}
<p><a href="clean_quotes.csv">清洗后的全部行情</a> · <a href="market_changes.csv">期间变化</a> · <a href="brief.md">简报文本</a></p>
<h2>2. 固收估值核对</h2><p class="muted">结算日 {escape(settings['business_date'])}，每 100 面值；Actual/Actual Bond、按票息频率复利、无节假日调整。QuantLib 与现金流折现双算。</p>{bond_table}
<p class="muted">DV01 是收益率上下平移 1bp 的中央差分价格变动。当前示例不是实际债券的结算约定。</p>
<h2>3. 需处理记录</h2><p class="muted">保留原始记录。冲突修订整组隔离；正常修订保留截止前最新版本。</p>{exception_table}
<p><a href="decisions.csv">全部处理记录</a> · <a href="source_findings.csv">行情源差异与缺失</a></p>
<h2>4. 需求反馈台账</h2><p class="muted">六条虚构反馈按“模块 + 规范化标题”合并。P1/P2/P3 来自影响与紧急程度的规则；业务负责人仍需确认。</p>{queue}
<p><a href="requirements.csv">下载需求台账</a></p>
<h2>5. 公开资料记录</h2><p class="muted">保留来源与待确认项，不对未试用的系统做性能或价格排名。</p>
<div class="scroll"><table><thead><tr><th>产品 / 来源</th><th>公开资料整理</th><th>待确认</th></tr></thead><tbody>{sources}</tbody></table></div>
<footer class="muted">Python + QuantLib 1.43。数据、反馈和异常均为模拟；输入摘要见 <a href="manifest.json">复现清单</a>。</footer>
</main></body></html>\n"""
