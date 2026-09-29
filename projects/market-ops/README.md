# 市场数据核对与运营简报

一个金融投资运营练习：接收两路行情文件，保留原始记录，整理异常和需求反馈，再生成一份可直接阅读的简报。覆盖固定收益、股票和期货；不接实盘或付费终端。

先看 [样例简报](examples/demo/brief.md)，再看 [处理记录](examples/demo/decisions.csv)。[HTML 报告](examples/demo/report.html)下载后可直接打开，CSV 使用 UTF-8 BOM，便于在 Excel 中查看。

## 做了什么

- 统一债券收益率的百分比 / 小数单位，检查时间顺序、缺失字段、非有限数、双边报价和成交量。
- 对正常修订保留截止前最新版本；同时间冲突整组隔离；截止后到达的数据不进入当日结果。
- 对比同日两路数据源，列出来源差异和当天缺失，不向前填充为当天行情。
- 用 QuantLib 计算固定利率债券净价、全价、应计利息、修正久期和 DV01，另用现金流折现式核对价格。
- 整理公开产品资料，保留来源、查阅日期和待确认项；将模拟反馈转成带验收条件的需求台账。

样例有 6 个虚构标的、2 路数据源、6 个观察日，共 83 行原始行情：69 行保留、10 行隔离、2 行截止后、2 行修订或重传。6 条虚构反馈合并为 4 个问题。21 项测试覆盖这些处理边界。

## 运行

Python 3.10 及以上，依赖 QuantLib 1.43。

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
python -m pip install -e .
market-ops demo --output outputs/demo
python -m unittest discover -s tests -v
```

复算公开样例，或替换为同格式的授权数据：

```bash
market-ops run --input examples/demo/inputs --output outputs/recheck
```

## 文件怎么读

| 文件 | 用途 |
|---|---|
| `report.html` / `brief.md` | 当日覆盖、市场变化、异常、需求和资料记录 |
| `clean_quotes.csv` | 统一单位后的有效历史行情；保留来源和原始行号 |
| `decisions.csv` | 所有原始行的处理结果，四类状态互斥且合计等于原始行数 |
| `source_findings.csv` | 同日来源差异与当天缺失 |
| `bond_checks.csv` | 结算日、收益率、净价、全价、DV01 和折现复核差 |
| `requirements.csv` | 合并后的反馈、优先级规则、证据编号与验收条件 |
| `manifest.json` | 输入文件 SHA-256、参数、QuantLib 版本 |

## 说明

- [输入与处理口径](docs/input-and-rules.md)
- [样例复核记录](docs/sample-review.md)
- [公开资料与竞品记录](docs/product-notes.md)
- [实现记录与下一步](docs/development-notes.md)

公开行情、订单编号和用户反馈均为模拟。竞品信息来自公开介绍，未对商业终端进行实测。报价阈值、优先级及债券约定只用于演示。
