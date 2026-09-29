# RiskLens

投资组合风险与下单前审查的研究原型。把风险计算、政策检查和证据记录放在同一条流程里，方便定位“哪个风险超限、哪笔订单需要复核、依据是什么”。

默认样例使用六类模拟资产、756 个工作日收益和五笔虚构订单。所有政策阈值都是演示用的内部设定，不是法定限额。项目没有实盘接口，也不做违法认定。

## 看什么

- [样例结果与观察](docs/results.md)：指标、订单反例和当前限制。
- [方法说明](docs/methodology.md)：VaR / ES 口径、滚动回测、压力测试与政策边界。
- [输入格式](docs/data-contract.md)：CSV 字段与检查要求。
- [AI 协作记录](docs/ai-collaboration.md)：本项目如何使用 AI，以及哪些输出需要独立验证。
- [完整结果](examples/demo/summary.json)与[HTML 报告](examples/demo/report.html)：下载报告后直接用浏览器打开，支持压力试算与告警筛选。

## 复现

Python 3.10 及以上。从仓库根目录运行：

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
python -m pip install -e .
risklens demo --output outputs/demo
python -m unittest discover -s tests -v
```

离线环境已有 NumPy 和 pandas 时，可直接运行：

```bash
# PowerShell
$env:PYTHONPATH="src"
python -m risklens.cli demo --output outputs/demo
```

macOS / Linux 对应命令为 `PYTHONPATH=src python -m risklens.cli demo --output outputs/demo`。

## 计算与检查

1. 输入校验：日期顺序、重复记录、缺失值、未来日期、未知资产和负持仓。
2. 市场风险：一日历史 VaR / ES、协方差波动贡献、重建路径回撤。
3. 回测：每一天只使用此前 252 日，记录突破并计算 Kupiec 覆盖率检验。
4. 压力测试：股票、利率和黄金冲击；债券使用修正久期近似。
5. 政策检查：单一资产和行业集中度、风险预算、流动性、估值时效，以及订单的限制名单、KYC、适当性、ADV 参与率、现金 / 持仓与买入后集中度。
6. 输出：数值报告、订单检查、规则版本、证据编号和输入文件 SHA-256。

订单检查逐笔使用同一个快照，不累计执行。一个订单通过演示规则，并不意味着它通过其他业务、法律或监管要求。当前已有持仓超限和订单检查结果分别记录。

## 项目结构

```text
src/risklens/
  data.py         模拟样例与输入校验
  risk.py         尾部风险、回测、压力测试
  compliance.py   11 类政策规则与证据记录
  ai_review.py    离线证据包与模型数值引用校验
  report.py       本地 HTML 报告
  cli.py          命令行入口
config/           带版本号的演示政策
tests/            金融口径、时点反例、规则边界和复现测试
examples/demo/    可直接阅读的样例输入与输出
docs/             方法、结果和协作说明
```

## AI 辅助复核

主流程不需要模型或 API Key。运行时会生成 `ai_evidence_pack.json`，可交给模型整理观察，再对模型返回的证据引用和数值进行校验：

```bash
risklens validate-review --pack outputs/demo/ai_evidence_pack.json --response response.json
```

只校验证据是否存在及显式数值是否一致，不能证明自由文本正确。评论需要人工语义审阅。该接口是可选的离线扩展；本项目未实现在线模型调用。

## 当前边界

这是研究原型。真实应用还需要价格与持仓核对、业务适用性评审、挂单冻结、批量限额、交易成本、审查权限与复核闭环。收益是以当前固定权重重建的模拟路径，不能当作策略业绩；压力场景没有概率含义。

参考材料及与本实现的差异见[方法说明](docs/methodology.md)。
