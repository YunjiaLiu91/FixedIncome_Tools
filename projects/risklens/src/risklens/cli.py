"""Command line entry point; identical code for generated and supplied CSV inputs."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from .ai_review import evidence_pack, validate_claims
from .compliance import check
from .data import generate, load_inputs, load_policy, validate
from .report import write_report
from .risk import analyse


def write_json(path: Path, payload):
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def run(output: Path, policy_path: Path, seed: int = 42, input_dir: Path | None = None):
    policy = load_policy(policy_path)
    returns, positions, orders = load_inputs(input_dir) if input_dir else generate(seed)
    validate(returns, positions, orders, policy)
    risk, backtest, portfolio = analyse(returns, positions, policy)
    checks, decisions = check(positions, orders, risk, policy)
    output.mkdir(parents=True, exist_ok=True)
    returns.to_csv(output / "returns.csv", float_format="%.17g")
    positions.to_csv(output / "positions.csv", index=False)
    orders.to_csv(output / "orders.csv", index=False)
    backtest.to_csv(output / "backtest.csv", index=False)
    portfolio.to_csv(output / "portfolio_returns.csv", float_format="%.17g")
    write_json(output / "policy.json", policy)
    write_json(output / "risk.json", risk)
    write_json(output / "checks.json", checks)
    write_json(output / "order_decisions.json", decisions)
    write_json(output / "ai_evidence_pack.json", evidence_pack(risk, checks))
    files = ["returns.csv", "positions.csv", "orders.csv", "policy.json"]
    hashes = {name: hashlib.sha256((output / name).read_bytes()).hexdigest() for name in files}
    payload = dict(project="RiskLens", version="0.1.0", as_of=policy["as_of"], policy_version=policy["version"],
                   data_source="user_supplied_csv" if input_dir else "synthetic", seed=None if input_dir else seed,
                   input_hashes=hashes, policy=policy, risk=risk, checks=checks, order_decisions=decisions,
                   sample=dict(days=len(returns), assets=len(positions), orders=len(orders)),
                   counts=dict(checks=len(checks), failures=sum(not c["passed"] for c in checks),
                               blocked_orders=sum(d["status"] == "BLOCK" for d in decisions)),
                   notes=["Fictional internal policy; no legal or regulatory certification",
                          "Each order is checked independently against the same snapshot, not cumulatively",
                          "AI is optional offline commentary; numerical checks do not verify prose semantics"])
    write_json(output / "summary.json", payload)
    write_report(output / "report.html", payload, portfolio, backtest)
    return payload


def main():
    parser = argparse.ArgumentParser(description="Explainable risk and pre-trade compliance demo")
    sub = parser.add_subparsers(dest="command", required=True)
    demo = sub.add_parser("demo")
    demo.add_argument("--output", type=Path, default=Path("outputs/demo"))
    demo.add_argument("--policy", type=Path, default=Path("config/policy.json"))
    demo.add_argument("--seed", type=int, default=42)
    custom = sub.add_parser("analyse")
    custom.add_argument("--input", type=Path, required=True)
    custom.add_argument("--output", type=Path, default=Path("outputs/custom"))
    custom.add_argument("--policy", type=Path, required=True)
    review = sub.add_parser("validate-review")
    review.add_argument("--pack", type=Path, required=True)
    review.add_argument("--response", type=Path, required=True)
    review.add_argument("--output", type=Path, default=Path("validated_claims.json"))
    args = parser.parse_args()
    if args.command == "validate-review":
        result = validate_claims(json.loads(args.response.read_text(encoding="utf-8")),
                                 json.loads(args.pack.read_text(encoding="utf-8")))
        write_json(args.output, result)
        print("Numerical references verified. Human review of comments is still required.")
    else:
        result = run(args.output, args.policy, getattr(args, "seed", 42), getattr(args, "input", None))
        print(json.dumps(dict(sample=result["sample"], counts=result["counts"], report=str(args.output / "report.html")), ensure_ascii=False))


if __name__ == "__main__":
    main()
