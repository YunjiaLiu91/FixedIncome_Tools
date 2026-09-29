# 输入格式

从仓库根目录运行 `risklens analyse --input path/to/csv --policy config/policy.json`。输入目录需要三个 CSV，结构与 `examples/demo` 一致。policy.as_of 必须与收益序列最后日期一致。

| 文件 | 字段 | 约束 |
|---|---|---|
| returns.csv | date，各资产 symbol 列 | 日期唯一递增，有限数值，简单日收益大于 −100% |
| positions.csv | symbol, sector, asset_class | 资产唯一，与收益列完全相同；类别为 equity / bond / gold / cash |
| positions.csv | market_value, adv_cny | CNY，非负持仓，正 ADV，总 NAV 为正 |
| positions.csv | duration, risk_level, price_date | 非负修正久期，1–5 整数风险等级，估值日期不得在未来 |
| orders.csv | order_id, symbol, side, notional_cny | 唯一订单编号，已知非现金资产，BUY / SELL，正名义金额 |
| orders.csv | kyc_expiry, client_risk_level | 到期日期、1–5 整数客户风险等级 |

必须有且只有一个现金资产。单一币种、无空头、无杠杆、无衍生品。不同币种需先形成明确的汇率估值与收益口径，不能直接混合。

ADV 是固定输入代理，未实现历史滚动成交量。工作日样例由 pandas 的 bdate_range 生成，没有真实交易所节假日日历。估值日期年龄以自然日计算。

每笔订单独立审查当前快照。不能将多笔通过结果视为整个订单批次可执行；尚未实现冻结资金、交易费用、部分成交和累计额度。

输出中 `data_source=user_supplied_csv` 只表示读取了用户文件，不验证供应商、复权、行情真实性或历史持仓一致性。
