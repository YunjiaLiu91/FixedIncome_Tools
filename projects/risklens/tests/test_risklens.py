import copy
import json
from pathlib import Path
import tempfile
import unittest

import numpy as np
import pandas as pd

from risklens.ai_review import evidence_pack, validate_claims
from risklens.cli import run
from risklens.compliance import check
from risklens.data import generate, load_policy, validate
from risklens.risk import analyse, coverage_test, historical_tail, max_drawdown, rolling_var_backtest

ROOT = Path(__file__).resolve().parents[1]


class TailRiskTests(unittest.TestCase):
    def test_fractional_tail_has_exact_mass(self):
        var, es = historical_tail([0, -0.01, -0.02, -0.03], 0.625)
        self.assertAlmostEqual(var, 0.02)
        self.assertAlmostEqual(es, (0.03 + 0.5 * 0.02) / 1.5)

    def test_ties_and_zero_risk(self):
        self.assertEqual(historical_tail([-0.02] * 10), (0.02, 0.02))
        self.assertEqual(historical_tail([0.01] * 10), (0, 0))

    def test_small_tail_uses_worst_loss(self):
        self.assertEqual(historical_tail([-0.01, -0.05], 0.99), (0.05, 0.05))

    def test_drawdown_includes_first_day_loss(self):
        self.assertAlmostEqual(max_drawdown([-0.2, 0.1]), -0.2)

    def test_invalid_returns_rejected(self):
        for series in [[], [np.nan], [np.inf], [[0.1]]]:
            with self.assertRaises(ValueError):
                historical_tail(series)

    def test_rolling_var_excludes_current_and_future_returns(self):
        dates = pd.bdate_range("2020-01-01", periods=12)
        base = pd.Series(np.linspace(-0.01, 0.01, 12), index=dates)
        changed = base.copy()
        changed.iloc[6:] = -0.8
        first = rolling_var_backtest(base, 6, 0.975)
        second = rolling_var_backtest(changed, 6, 0.975)
        self.assertEqual(first.iloc[0].var_fraction, second.iloc[0].var_fraction)
        self.assertNotEqual(first.iloc[0].realized_loss, second.iloc[0].realized_loss)

    def test_coverage_extremes_remain_finite(self):
        for breaches in [[False] * 100, [True] * 100]:
            result = coverage_test(breaches, 0.975)
            self.assertTrue(np.isfinite(result["kupiec_lr"]))
            self.assertTrue(0 <= result["kupiec_pvalue"] <= 1)


class ControlsTests(unittest.TestCase):
    def setUp(self):
        self.returns, self.positions, self.orders = generate()
        self.policy = load_policy(ROOT / "config/policy.json")
        self.risk, self.bt, _ = analyse(self.returns, self.positions, self.policy)

    def test_risk_contributions_sum_to_volatility(self):
        self.assertAlmostEqual(sum(a["volatility_contribution"] for a in self.risk["assets"]),
                               self.risk["annualized_volatility"])

    def test_stress_matches_hand_calculation(self):
        # 70% equity, 18% bonds at duration 4.5, 7% gold and 5% cash.
        expected = 7e6 * -0.2 + 1.8e6 * -4.5 * 0.01 + 0.7e6 * 0.05
        self.assertAlmostEqual(self.risk["scenarios"][0]["pnl_cny"], expected)

    def test_injected_orders_and_clean_controls(self):
        checks, decisions = check(self.positions, self.orders, self.risk, self.policy)
        by_id = {d["order_id"]: d for d in decisions}
        self.assertEqual(by_id["ORD-001"]["failed_rules"], ["O01"])
        self.assertEqual(set(by_id["ORD-002"]["failed_rules"]), {"O02", "O03", "O04", "O05", "O06"})
        self.assertEqual(by_id["ORD-003"]["status"], "PASS_DEMO_CHECKS")
        self.assertEqual(by_id["ORD-004"]["status"], "PASS_DEMO_CHECKS")
        self.assertEqual(by_id["ORD-005"]["failed_rules"], ["O05"])
        self.assertTrue(all(len(c["evidence_id"]) == 16 for c in checks))

    def test_kyc_expiry_on_asof_day_is_valid(self):
        self.orders.loc[0, "kyc_expiry"] = self.policy["as_of"]
        checks, _ = check(self.positions, self.orders, self.risk, self.policy)
        self.assertTrue(next(c for c in checks if c["entity"] == "ORD-001" and c["rule_id"] == "O02")["passed"])

    def test_stale_price_is_a_failed_check(self):
        self.positions.loc[0, "price_date"] = "2026-09-01"
        checks, _ = check(self.positions, self.orders, self.risk, self.policy)
        self.assertFalse(next(c for c in checks if c["entity"] == "SIM_TECH_A" and c["rule_id"] == "P05")["passed"])

    def test_evidence_changes_with_policy_version(self):
        first, _ = check(self.positions, self.orders, self.risk, self.policy)
        altered = dict(self.policy, version="v2")
        second, _ = check(self.positions, self.orders, self.risk, altered)
        self.assertNotEqual(first[0]["evidence_id"], second[0]["evidence_id"])

    def test_missing_returns_rejected_instead_of_filled(self):
        self.returns.iloc[0, 0] = np.nan
        with self.assertRaisesRegex(ValueError, "NaN"):
            validate(self.returns, self.positions, self.orders, self.policy)

    def test_unknown_symbol_rejected(self):
        self.orders.loc[0, "symbol"] = "UNKNOWN"
        with self.assertRaisesRegex(ValueError, "known non-cash"):
            validate(self.returns, self.positions, self.orders, self.policy)

    def test_future_price_and_return_rejected(self):
        self.positions.loc[0, "price_date"] = "2026-09-29"
        with self.assertRaisesRegex(ValueError, "future price"):
            validate(self.returns, self.positions, self.orders, self.policy)
        self.positions.loc[0, "price_date"] = "2026-09-28"
        altered = dict(self.policy, as_of="2026-09-25")
        with self.assertRaisesRegex(ValueError, "future observations"):
            validate(self.returns, self.positions, self.orders, altered)

    def test_duplicate_dates_and_orders_rejected(self):
        dates = self.returns.index.tolist()
        dates[1] = dates[0]
        self.returns.index = pd.DatetimeIndex(dates)
        with self.assertRaisesRegex(ValueError, "unique and sorted"):
            validate(self.returns, self.positions, self.orders, self.policy)
        self.returns, _, _ = generate()
        self.orders.loc[1, "order_id"] = "ORD-001"
        with self.assertRaisesRegex(ValueError, "duplicate order"):
            validate(self.returns, self.positions, self.orders, self.policy)

    def test_zero_adv_and_negative_holdings_rejected(self):
        self.positions.loc[0, "adv_cny"] = 0
        with self.assertRaisesRegex(ValueError, "ADV"):
            validate(self.returns, self.positions, self.orders, self.policy)
        self.positions.loc[0, "adv_cny"] = 1e6
        self.positions.loc[0, "market_value"] = -1
        with self.assertRaisesRegex(ValueError, "numeric"):
            validate(self.returns, self.positions, self.orders, self.policy)


class AIReviewTests(unittest.TestCase):
    def setUp(self):
        self.pack = {"facts": {"METRIC:VAR_CNY": {"value": 100_000.0, "unit": "CNY"}}}
        self.good = {"observations": [{"fact_id": "METRIC:VAR_CNY", "value": 100_000.0, "comment": "待审阅"}]}

    def test_supported_number_verified_with_semantic_caveat(self):
        result = validate_claims(self.good, self.pack)
        self.assertTrue(result["numerical_claims_verified"])
        self.assertEqual(result["semantic_review"], "REQUIRED_BY_HUMAN")

    def test_invented_number_rejected(self):
        bad = copy.deepcopy(self.good)
        bad["observations"][0]["value"] = 999_999
        with self.assertRaisesRegex(ValueError, "unsupported number"):
            validate_claims(bad, self.pack)

    def test_invented_reference_rejected(self):
        bad = copy.deepcopy(self.good)
        bad["observations"][0]["fact_id"] = "NONEXISTENT"
        with self.assertRaisesRegex(ValueError, "unknown evidence"):
            validate_claims(bad, self.pack)

    def test_boolean_nan_and_extra_fields_rejected(self):
        for value in [True, np.nan]:
            bad = copy.deepcopy(self.good)
            bad["observations"][0]["value"] = value
            with self.assertRaises(ValueError):
                validate_claims(bad, self.pack)
        with self.assertRaises(ValueError):
            validate_claims(dict(self.good, trade="BUY"), self.pack)


class IntegrationTests(unittest.TestCase):
    def test_reproducible_outputs_and_custom_csv_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            first = run(root / "a", ROOT / "config/policy.json")
            second = run(root / "b", ROOT / "config/policy.json")
            self.assertEqual(first, second)
            self.assertEqual(first["sample"], {"days": 756, "assets": 6, "orders": 5})
            self.assertEqual(first["counts"]["blocked_orders"], 3)
            self.assertEqual(first["risk"]["backtest"]["observations"], 504)
            html = (root / "a/report.html").read_text(encoding="utf-8")
            self.assertNotIn("@@", html)
            custom = run(root / "c", ROOT / "config/policy.json", input_dir=root / "a")
            self.assertAlmostEqual(first["risk"]["es_cny"], custom["risk"]["es_cny"], places=6)
            pack = json.loads((root / "a/ai_evidence_pack.json").read_text(encoding="utf-8"))
            self.assertEqual(pack["mode"], "offline, no external model called")


if __name__ == "__main__":
    unittest.main()
