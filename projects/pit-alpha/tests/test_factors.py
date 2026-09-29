import unittest

import numpy as np
import pandas as pd

from fundamental_alpha.factors import build_factors
from fundamental_alpha.synthetic import generate_demo_data
from fundamental_alpha.point_in_time import align_fundamentals_asof


class FactorTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fundamentals, market = generate_demo_data(n_stocks=60, start="2020-01-31", end="2021-12-31")
        cls.panel = build_factors(align_fundamentals_asof(market, fundamentals))

    def test_factor_is_cross_sectionally_standardized(self):
        means = self.panel.groupby("date")["factor_composite"].mean().abs()
        stds = self.panel.groupby("date")["factor_composite"].std(ddof=0)
        self.assertLess(float(means.max()), 1e-10)
        self.assertLess(float((stds - 1.0).abs().max()), 1e-10)

    def test_size_exposure_is_neutralized(self):
        correlations = self.panel.groupby("date").apply(
            lambda g: g["factor_quality"].corr(np.log(g["market_cap"])),
            include_groups=False,
        )
        self.assertLess(float(correlations.abs().max()), 1e-10)


if __name__ == "__main__":
    unittest.main()

