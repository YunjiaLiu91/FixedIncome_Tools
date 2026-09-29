# Point-in-Time Fundamental Alpha Research

本项目实现了一套月频股票基本面因子研究流程，重点处理财务数据的可见时点、截面因子构建、风险中性化与样本外评估。目前研究对象包括质量、价值和成长三个基础信号，并以固定权重构建复合因子。

> 仓库中的默认实验使用模拟数据，目的是验证研究流程和代码逻辑。报告中的收益指标不代表真实投资表现；因子的实际有效性需要使用真实 point-in-time 数据重新检验。

## 研究问题

当前版本考察三个基础信号：

1. **质量（Quality）**：高 ROE、高经营现金流、低应计利润的公司，未来收益是否更高？
2. **价值（Value）**：在同行和相近规模公司中，估值较低的公司是否有超额收益？
3. **成长（Growth）**：收入增速较高的公司是否存在可持续的横截面收益？

最终信号是 `50% 质量 + 30% 价值 + 20% 成长`，每月调仓。所有财报字段只在 `announce_date <= signal_date` 时可见，避免未来数据泄漏；随后进行稳健去极值、标准化以及行业和对数市值中性化。

多空组合采用 50% 做多最高组、50% 做空最低组，总敞口为 100%。`long_short = 0.5 × (Q5 − Q1)`；未缩放的组间收益差单独保存在 `quantile_spread`，报告收益与持仓权重使用同一口径。

## 运行方式

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -e .
fundamental-alpha demo --output outputs/demo
python -m unittest discover -s tests -v
```

如果尚未安装为命令，也可以直接运行：

```bash
PYTHONPATH=src python -m fundamental_alpha.cli demo --output outputs/demo
```

运行后会生成：

- `aligned_panel.csv`：每个交易月可见的最新财报快照与因子值；
- `monthly_ic.csv`：月度 Rank IC；
- `quantile_returns.csv`：五分组和多空收益；
- `decay.csv`：1/3/6 个月信号衰减；
- `summary.json`：核心指标；
- `data_quality.json`：输入完整性和 PIT 对齐覆盖率；
- `experiment_manifest.json`：本次实验的因子定义、预处理和验证参数；
- `report.html`：可直接用浏览器打开的研究报告。

## 研究流程

```text
财报（报告期、公告日） ─┐
                       ├─> PIT 对齐 ─> 去极值/标准化 ─> 行业+市值中性化
行情（调仓日、未来收益） ┘                                      │
                                                               v
                              IC/IR、分层、多空、换手、衰减、容量、样本外
```

## 实现重点

- **数据时点**：使用公告日而非报告期连接财务数据，并通过断言和单元测试检查未来信息。
- **因子处理**：各项指标在月度截面上进行 MAD 去极值、标准化，再对行业和对数市值做中性化。
- **评价维度**：除收益和 Sharpe 外，同时观察 Rank IC、ICIR、分层单调性、换手、衰减、风格暴露和容量代理。
- **样本外检验**：预先固定时间切分与复合权重，样本外区间不参与参数选择。
- **实验复现**：随机种子、命令行入口、结构化结果和测试均保存在仓库中。

## 项目结构

```text
src/fundamental_alpha/
  synthetic.py      # 生成可复现的财务与行情演示数据
  point_in_time.py  # 按公告日做 as-of join，并检查未来数据
  factors.py        # 因子构建、去极值、标准化、中性化
  diagnostics.py    # 数据缺失、重复、覆盖率和时点检查
  evaluation.py     # IC、分层、换手、衰减、容量和样本外评估
  report.py         # 生成无外部依赖的 HTML 研究报告
  pipeline.py       # 串联完整实验
  cli.py            # 命令行入口
tests/              # 数据时点与计算逻辑测试
docs/               # 方法说明、数据接入和研究复盘
```

## 复现与阅读

1. 运行 demo，并打开 `outputs/demo/report.html` 检查结果。
2. [研究过程 Notebook](notebooks/01_factor_research.ipynb) 按执行顺序展示数据、因子和评价结果。
3. [完整研究记录](docs/05_研究过程记录.md) 记录假设、口径、质量检查和实验结论。
4. [因子研究方法说明](docs/01_因子研究方法.md) 记录指标含义和评价口径。
5. `point_in_time.py` 是数据时点处理的核心实现，`tests/test_point_in_time.py` 给出了最小反例。
6. `factors.py` 实现截面处理和风险中性化，`evaluation.py` 实现各项诊断指标。
7. [真实数据接入说明](docs/02_真实数据接入.md) 定义了输入字段和 A 股数据检查项。
8. [研究复盘与常见问题](docs/03_研究复盘与常见问题.md) 说明主要方法选择及其局限。
9. [后续研究计划](docs/04_后续研究计划.md) 记录真实数据验证和扩展方向。

## 当前局限与下一步

当前版本采用月频截面和等权多空组合，主要用于验证研究流程。尚未覆盖历史股票池、退市样本、财报更正版本、停牌和涨跌停约束，也没有使用非线性冲击成本模型。接入真实数据后，将先完成这些基础校验，再考虑分析师预期、行业景气和文本类信号。
