"""Deliberately imperfect input, so the exception workflow can be inspected."""

import csv
from datetime import date
import json
from pathlib import Path


def write_csv(path, rows, fields=None):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields if fields is not None else list(rows[0]) if rows else [])
        writer.writeheader()
        writer.writerows(rows)


def write_sample(target):
    target = Path(target)
    target.mkdir(parents=True, exist_ok=True)
    rows = []
    for symbol, name, asset, issue, maturity, coupon, freq in [
        ("SIM_BOND_3", "样例国债 A", "bond", "2024-09-28", "2029-09-28", "3.0", "2"),
        ("SIM_BOND_10", "样例国债 B", "bond", "2024-06-15", "2034-06-15", "2.7", "2"),
        ("SIM_EQ_A", "样例股票 A", "equity", "", "", "", ""),
        ("SIM_EQ_B", "样例股票 B", "equity", "", "", "", ""),
        ("SIM_IF", "样例股指期货", "future", "", "2026-12-18", "", ""),
        ("SIM_T", "样例国债期货", "future", "", "2026-12-18", "", ""),
    ]:
        rows.append(dict(instrument_id=symbol, name=name, asset_class=asset, currency="CNY",
                         issue_date=issue, maturity_date=maturity, coupon_pct=coupon, frequency=freq))
    write_csv(target / "instruments.csv", rows)
    quotes = []
    days = ["2026-09-21", "2026-09-22", "2026-09-23", "2026-09-24", "2026-09-25", "2026-09-28"]
    paths = [[2.08, 2.07, 2.10, 2.09, 2.06, 2.04], [2.70, 2.68, 2.69, 2.66, 2.65, 2.63],
             [24.5, 24.8, 24.6, 25.0, 24.9, 25.2], [18.0, 17.9, 18.1, 18.3, 18.0, 18.2],
             [3920, 3940, 3910, 3950, 3945, 3980], [103.1, 103.15, 103.0, 103.05, 103.2, 103.3]]
    for index, day in enumerate(days):
        for n, instrument in enumerate(rows):
            if instrument["instrument_id"] == "SIM_T" and day == days[-1]:
                continue
            for vendor in ["feed_a", "feed_b"]:
                asset = instrument["asset_class"]
                unit = "yield_pct" if asset == "bond" else "cny" if asset == "equity" else "points"
                mid = paths[n][index] + (0.002 if asset == "bond" else 0.01) * (vendor == "feed_b")
                if n == 1 and day == days[-1] and vendor == "feed_b":
                    mid = 2.82
                spread = 0.005 if asset == "bond" else 0.05 if asset == "equity" else 0.1
                factor = 0.01 if asset == "bond" and vendor == "feed_b" else 1
                if factor == 0.01:
                    unit = "yield_decimal"
                quotes.append(dict(record_id=f"Q{len(quotes)+1:03d}", instrument_id=instrument["instrument_id"],
                                   asof_date=day, vendor=vendor, published_at=f"{day}T16:10:00+08:00",
                                   ingested_at=f"{day}T16:12:00+08:00", bid=f"{(mid-spread)*factor:.8f}",
                                   ask=f"{(mid+spread)*factor:.8f}", mid=f"{mid*factor:.8f}",
                                   volume=str(1000 + 30 * index + n), quote_unit=unit))

    def base(symbol="SIM_EQ_A", day=days[-1], vendor="feed_a"):
        return next(q for q in quotes if q["instrument_id"] == symbol and q["asof_date"] == day and q["vendor"] == vendor)

    # A valid intraday correction, plus an identical retransmission at the same timestamps.
    correction = dict(base("SIM_BOND_3"), record_id="REV001", published_at="2026-09-28T17:00:00+08:00",
                      ingested_at="2026-09-28T17:01:00+08:00", bid="2.050", mid="2.055", ask="2.060")
    quotes += [correction, dict(correction, record_id="REV002")]
    for record, changes in [
        ("ERR_UNKNOWN", {"instrument_id": "UNMAPPED"}),
        ("ERR_UNIT", {"quote_unit": "usd"}),
        ("ERR_CROSS", {"bid": "25.3", "ask": "25.1"}),
        ("ERR_MID", {"mid": "31"}),
        ("ERR_VOLUME", {"volume": "-5"}),
        ("ERR_NUMBER", {"mid": "NaN"}),
        ("ERR_TIME", {"ingested_at": "2026-09-28T15:00:00+08:00"}),
        ("ERR_TZ", {"published_at": "2026-09-28T16:10:00"}),
        ("LATE001", {"ingested_at": "2026-09-28T19:00:00+08:00"}),
        ("FUTURE001", {"asof_date": "2026-09-29", "published_at": "2026-09-29T16:10:00+08:00", "ingested_at": "2026-09-29T16:12:00+08:00"}),
    ]:
        quotes.append(dict(base(), record_id=record, **changes))
    # Same revision time, different payload: quarantine the whole group, including the older row.
    conflict = dict(base("SIM_EQ_B", days[-2]), record_id="CONFLICT001", bid="18.05", mid="18.10", ask="18.15")
    quotes.append(conflict)
    write_csv(target / "quotes.csv", quotes)

    feedback = []
    for ticket, role, module, title, impact, urgency, acceptance, evidence in [
        ("REQ001", "数据运营", "行情", "收益率百分比与小数混用", 3, 3, "2.04% 与 0.0204 合并后相同，并保留原单位", "REV001"),
        ("REQ002", "交易支持", "行情", "收益率百分比与小数混用", 3, 2, "导出表明确列出标准单位", "Q061"),
        ("REQ003", "交易支持", "行情", "国债期货最新行情缺失", 3, 2, "当天无行情时显示缺失日期，不沿用为当天价格", "SIM_T"),
        ("REQ004", "分析支持", "估值", "需要同时导出净价和全价", 2, 2, "全价等于净价加应计利息，写明结算日期", "SIM_BOND_3"),
        ("REQ005", "运营分析", "报表", "异常清单要带原始行号", 2, 1, "每条异常可回查原始 CSV 行号和记录编号", "ERR_UNIT"),
        ("REQ006", "数据运营", "报表", "异常清单要带原始行号", 1, 2, "隔离与修订记录都有来源编号", "CONFLICT001"),
    ]:
        feedback.append(dict(ticket_id=ticket, submitted_at="2026-09-28T17:20:00+08:00", role=role,
                             module=module, title=title, impact=impact, urgency=urgency,
                             acceptance=acceptance, evidence_ref=evidence))
    write_csv(target / "feedback.csv", feedback)
    sources = [
        dict(entry_id="SRC01", product="LSEG Workspace", asset_class="固收", observed_on="2026-09-29",
             publication_date="未标注", observation="公开介绍包含固收数据、价格与收益率分析、利率衍生品数据及 API 工作流。",
             follow_up="试用时核对字段单位、修订记录和导出权限。",
             url="https://www.lseg.com/en/data-analytics/products/workspace/fixed-income"),
        dict(entry_id="SRC02", product="Bloomberg Professional", asset_class="多资产", observed_on="2026-09-29",
             publication_date="未标注", observation="产品目录区分终端、数据、交易、风险和合规模块；数据目录包含时点数据与参考数据。",
             follow_up="需要授权环境确认字段完整性；本项目未实测终端。",
             url="https://professional.bloomberg.com/products/"),
        dict(entry_id="SRC03", product="QuantLib", asset_class="估值组件", observed_on="2026-09-29",
             publication_date="未标注", observation="开源量化金融库提供 Python 绑定，可作为固定利率债券估值核对组件。",
             follow_up="组件与商业终端功能层级不同，不做横向性能排名。",
             url="https://www.quantlib.org/"),
    ]
    write_csv(target / "sources.csv", sources)
    settings = dict(cutoff="2026-09-28T18:00:00+08:00", business_date="2026-09-28",
                    vendor_priority=["feed_a", "feed_b"], bond_gap_bp=5.0, price_gap_pct=1.0,
                    source_review_date="2026-09-29", sample_kind="synthetic", policy_version="ops-demo-1")
    (target / "settings.json").write_text(json.dumps(settings, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
