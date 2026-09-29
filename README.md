# FixedIncome_Tools

金融风险与量化研究作品。当前包含三个可独立运行的 Python 项目，侧重计算口径、数据时点和结果可追溯。

| 项目 | 研究内容 | 阅读入口 |
|---|---|---|
| RiskLens | 投资组合 VaR / ES、滚动回测、压力测试与交易前政策检查 | [项目说明](projects/risklens/README.md) · [结果与反例](projects/risklens/docs/results.md) |
| PIT Fundamental Alpha | 按财报公告日对齐的质量、价值、成长因子研究 | [项目说明](projects/pit-alpha/README.md) · [研究记录](projects/pit-alpha/docs/05_研究过程记录.md) |
| 市场数据核对与运营简报 | 固收、股票和期货数据清洗；QuantLib 债券估值核对；资料与需求台账 | [项目说明](projects/market-ops/README.md) · [样例简报](projects/market-ops/examples/demo/brief.md) |

## RiskLens

把风险计算和交易审查串在一起：六类资产、756 个工作日样例，11 类演示政策规则。输出实际值、阈值、规则版本与证据编号，便于复核集中度、流动性、KYC、适当性和订单资金问题。

默认运行完成 51 项检查，3 笔预设异常订单被阻拦，2 笔对照订单通过。数据和政策均为模拟设定，不代表真实识别率或监管认证。可选 AI 证据包用于整理解释，数值和订单判断由确定性代码完成。

## PIT Fundamental Alpha

财报只在公告后进入因子截面，进行去极值、标准化、行业与规模中性化，再检查 Rank IC、分层、换手和固定时间切分的样本外结果。公开样例为 180 只模拟股票、120 个月。

收益序列内置已知弱信号，只用于验证流程，不能推断真实投资收益。多空结果与 50% 多头、50% 空头持仓权重保持一致。

## 市场数据核对与运营简报

接收两路行情 CSV，保留原始记录，处理单位混用、修订冲突和截止后数据，标出同日来源差异与缺失。QuantLib 核对债券净价、全价及 DV01；公开产品资料保留原始链接，模拟用户反馈整理为需求台账。

样例包含 83 行模拟行情、6 条虚构反馈和 21 项测试。阅读 [简报](projects/market-ops/examples/demo/brief.md) 或下载 [HTML 报告](projects/market-ops/examples/demo/report.html)。复现：进入 `projects/market-ops`，执行 `python -m pip install -e .`，再运行 `market-ops demo --output outputs/demo`。

## 运行

三个项目分别安装，从对应目录执行：

```bash
cd projects/risklens
python -m pip install -e .
risklens demo --output outputs/demo
python -m unittest discover -s tests -v
```

```bash
cd projects/pit-alpha
python -m pip install -e .
fundamental-alpha demo --output outputs/demo
python -m unittest discover -s tests -v
```

