# 公开资料与竞品记录

查阅日期：2026-09-29。只记录公开说明能确认的内容。没有付费终端权限，没有比较价格、响应时间、字段覆盖率或用户满意度。网页未标注发布日期时，资料表记为“未标注”。

| 对象 | 公开资料能确认的内容 | 运营侧待确认事项 |
|---|---|---|
| LSEG Workspace 固收工作流 | 产品页包含固收定价与分析、利率衍生品数据、计算器和 API 工作流 | 字段单位、行情修订留痕、数据权限、Excel 导出及延迟处理 |
| Bloomberg Professional 产品目录 | 区分终端、数据、交易、风险和合规产品；数据目录列有时点数据、参考数据和价格数据 | 具体市场的字段覆盖；同一标的不同日期及版本怎样查询；导出权限 |
| QuantLib | 开源量化金融库，提供 Python 等语言绑定 | 合约条款、计息及结算约定是否一致；定价结果如何复核 |

来源：

- [LSEG Workspace for fixed income](https://www.lseg.com/en/data-analytics/products/workspace/fixed-income)
- [Bloomberg Professional 产品目录](https://professional.bloomberg.com/products/)
- [QuantLib 官方介绍](https://www.quantlib.org/)
- [QuantLib 官方 Python 债券函数测试](https://github.com/lballabio/QuantLib-SWIG/blob/master/Python/test/test_bondfunctions.py)

QuantLib 是组件，商业终端是工作流与数据产品，不能按同一维度打总分。对上述产品的待确认事项是本项目提出的检查问题，不是厂家已经承诺的功能。

## 信息整理模板

后续接入真实行业更新时，每条记录至少保留：原始链接、标题、发布日（若存在）、查阅日、涉及资产或模块、可确认事实、对当前工作的影响、需要谁复核。

当前只完成了三条公开产品资料的整理，未实现持续爬取、新闻订阅或自动判定行业趋势。
