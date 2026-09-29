"""Offline evidence pack and narrow numerical grounding checks for optional AI review."""

from __future__ import annotations

import math


def evidence_pack(risk: dict, checks: list[dict]) -> dict:
    facts = {"METRIC:VAR_CNY": dict(value=risk["var_cny"], unit="CNY"),
             "METRIC:ES_CNY": dict(value=risk["es_cny"], unit="CNY"),
             "METRIC:NAV_CNY": dict(value=risk["nav_cny"], unit="CNY")}
    for scenario in risk["scenarios"]:
        facts[f"STRESS:{scenario['name']}"] = dict(value=scenario["pnl_cny"], unit="CNY")
    for item in checks:
        if isinstance(item["actual"], (int, float)) and not isinstance(item["actual"], bool):
            facts[f"CHECK:{item['evidence_id']}"] = dict(value=item["actual"], unit=item["unit"], rule_id=item["rule_id"],
                                                         entity=item["entity"], status=item["status"], threshold=item["threshold"])
    return dict(data_source="synthetic", mode="offline, no external model called", facts=facts,
                instructions="仅从 facts 提取数值观察。每条返回 fact_id、value、comment；不得判断违法、推荐交易或宣称监管达标。comment 需要人工语义审阅。",
                response_schema={"observations": [{"fact_id": "METRIC:VAR_CNY", "value": risk["var_cny"], "comment": "人类审阅说明"}]})


def validate_claims(response: dict, pack: dict) -> dict:
    if set(response) != {"observations"} or not isinstance(response["observations"], list):
        raise ValueError("response must contain only an observations list")
    if not response["observations"] or len(response["observations"]) > 30:
        raise ValueError("1 to 30 observations required")
    verified = []
    for item in response["observations"]:
        if not isinstance(item, dict) or set(item) != {"fact_id", "value", "comment"}:
            raise ValueError("invalid observation schema")
        fact_id, value = item["fact_id"], item["value"]
        if not isinstance(fact_id, str) or fact_id not in pack["facts"]:
            raise ValueError(f"unknown evidence: {fact_id}")
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            raise ValueError("claim value must be finite numeric data")
        if not math.isclose(value, pack["facts"][fact_id]["value"], rel_tol=1e-6, abs_tol=1e-8):
            raise ValueError(f"unsupported number: {fact_id}")
        if not isinstance(item["comment"], str) or len(item["comment"]) > 1000:
            raise ValueError("comment must be a short string")
        verified.append(item)
    return dict(numerical_claims_verified=True, semantic_review="REQUIRED_BY_HUMAN", observations=verified,
                limitation="Only evidence references and explicit values are checked; free text may still contain misleading claims")
