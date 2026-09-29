import unittest

import pandas as pd

from fundamental_alpha.evaluation import monthly_rank_ic, quantile_returns, portfolio_weights, performance_summary
from fundamental_alpha.factors import build_factors
from fundamental_alpha.point_in_time import align_fundamentals_asof
from fundamental_alpha.synthetic import generate_demo_data


class EvaluationTest(unittest.TestCase):
    def test_reported_returns_match_actual_weights(self):
        panel = pd.DataFrame({
            "date": [pd.Timestamp("2024-01-31")] * 10,
            "symbol": [f"S{i}" for i in range(10)],
            "factor": list(range(10)), "forward_return": [i / 100 for i in range(10)],
            "adv20": [1e6] * 10,
        })
        weights = portfolio_weights(panel, "factor")
        realized = weights.merge(panel[["date", "symbol", "forward_return"]], on=["date", "symbol"])
        expected = (realized.weight * realized.forward_return).sum()
        reported = quantile_returns(panel, "factor").iloc[0]
        self.assertAlmostEqual(reported.long_short, expected)
        self.assertAlmostEqual(reported.quantile_spread, 2 * expected)

    def test_first_period_loss_counts_as_drawdown(self):
        summary = performance_summary(pd.Series([-0.2, 0.1]))
        self.assertAlmostEqual(summary["max_drawdown"], -0.2)

    def test_demo_signal_has_expected_direction(self):
        fundamentals, market = generate_demo_data(
            n_stocks=120, start="2018-01-31", end="2024-12-31", seed=7
        )
        panel = build_factors(align_fundamentals_asof(market, fundamentals))
        ic = monthly_rank_ic(panel, "factor_composite")
        quantiles = quantile_returns(panel, "factor_composite")
        self.assertGreater(ic["ic"].mean(), 0.01)
        self.assertGreater(quantiles["long_short"].mean(), 0.0)


if __name__ == "__main__":
    unittest.main()

