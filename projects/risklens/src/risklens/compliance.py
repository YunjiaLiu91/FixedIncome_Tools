"""Versioned fictional policy checks; alerts are evidence, not legal conclusions."""

from __future__ import annotations

import hashlib
import json

import pandas as pd


RULES = {
    "P01": ("单一资产集中度", "max_asset_weight"),
    "P02": ("行业集中度", "max_sector_weight"),
    "P03": ("单日 VaR 预算", "max_var_fraction"),
    "P04": ("持仓流动性", "max_liquidation_days"),
    "P05": ("估值时效", "max_price_age_days"),
    "O01": ("限制交易名单", "restricted_symbols"),
    "O02": ("KYC 有效期", "as_of"),
    "O03": ("产品与客户风险等级", "position/client risk level"),
    "O04": ("订单 ADV 参与率", "max_order_adv_fraction"),
    "O05": ("可用现金或持仓", "snapshot cash/holding"),
    "O06": ("买入后单一资产集中度", "max_asset_weight"),
}


def check(positions: pd.DataFrame, orders: pd.DataFrame, risk: dict, policy: dict) -> tuple[list[dict], list[dict]]:
    checks = []
    version, nav = policy["version"], risk["nav_cny"]

    def record(rule, entity, actual, threshold, passed, unit, explanation):
        title = RULES[rule][0]
        evidence = dict(rule_id=rule, policy_version=version, entity=entity, actual=actual,
                        threshold=threshold, passed=bool(passed), unit=unit)
        identifier = hashlib.sha256(json.dumps(evidence, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:16]
        checks.append(dict(evidence_id=identifier, title=title, status="PASS" if passed else "FAIL",
                           explanation=explanation, **evidence))

    p = positions.set_index("symbol")
    for asset in risk["assets"]:
        if asset["asset_class"] != "cash":
            record("P01", asset["symbol"], asset["weight"], policy["max_asset_weight"],
                   asset["weight"] <= policy["max_asset_weight"], "fraction", "非现金资产当前权重不超过内部上限")
            record("P04", asset["symbol"], asset["liquidation_days"], policy["max_liquidation_days"],
                   asset["liquidation_days"] <= policy["max_liquidation_days"], "days", "当前市值 / (ADV × 固定参与率)，不包含市场冲击")
        age = int((pd.Timestamp(policy["as_of"]) - pd.Timestamp(p.loc[asset["symbol"], "price_date"])).days)
        record("P05", asset["symbol"], age, policy["max_price_age_days"], age <= policy["max_price_age_days"],
               "calendar_days", "估值日期超过阈值时进入复核，不自动替换价格")
    sectors = positions[positions.asset_class != "cash"].groupby("sector").market_value.sum() / nav
    for sector, weight in sectors.items():
        record("P02", sector, float(weight), policy["max_sector_weight"], weight <= policy["max_sector_weight"],
               "fraction", "非现金行业市值 / 含现金 NAV")
    record("P03", "PORTFOLIO", risk["var_fraction"], policy["max_var_fraction"],
           risk["var_fraction"] <= policy["max_var_fraction"], "fraction", "指定窗口与置信度下的一日历史模拟 VaR")
    cash = float(positions.loc[positions.asset_class == "cash", "market_value"].sum())
    decisions = []
    for order in orders.itertuples():
        asset = p.loc[order.symbol]
        start = len(checks)
        restricted = order.symbol in policy["restricted_symbols"]
        record("O01", order.order_id, restricted, False, not restricted, "boolean", "演示名单同时限制买入和卖出，真实处置流程需另行定义")
        expiry = str(pd.Timestamp(order.kyc_expiry).date())
        record("O02", order.order_id, expiry, policy["as_of"], expiry >= policy["as_of"], "date", "KYC 到期日含当日有效")
        record("O03", order.order_id, int(asset.risk_level), int(order.client_risk_level),
               order.side == "SELL" or asset.risk_level <= order.client_risk_level, "level", "买入时产品等级不高于客户等级；卖出减仓不受该规则阻拦")
        participation = float(order.notional_cny / asset.adv_cny)
        record("O04", order.order_id, participation, policy["max_order_adv_fraction"],
               participation <= policy["max_order_adv_fraction"], "fraction", "单笔名义金额 / ADV；多订单累积参与率尚未实现")
        available = cash if order.side == "BUY" else float(asset.market_value)
        record("O05", order.order_id, float(order.notional_cny), available, order.notional_cny <= available,
               "CNY", "每笔订单独立对比快照现金或持仓；尚未扣除手续费与其他挂单冻结")
        projected = float((asset.market_value + (1 if order.side == "BUY" else -1) * order.notional_cny) / nav)
        record("O06", order.order_id, projected, policy["max_asset_weight"],
               order.side == "SELL" or projected <= policy["max_asset_weight"], "fraction", "买入后权重不超过上限；卖出以可用持仓规则约束")
        failures = [c for c in checks[start:] if not c["passed"]]
        decisions.append(dict(order_id=order.order_id, symbol=order.symbol, side=order.side,
                              status="BLOCK" if failures else "PASS_DEMO_CHECKS",
                              failed_rules=[c["rule_id"] for c in failures],
                              evidence_ids=[c["evidence_id"] for c in failures]))
    return checks, decisions
