import unittest

import pandas as pd

from fundamental_alpha.point_in_time import align_fundamentals_asof


class PointInTimeTest(unittest.TestCase):
    def test_statement_is_invisible_before_announcement(self):
        market = pd.DataFrame(
            {
                "date": pd.to_datetime(["2024-04-20", "2024-05-01"]),
                "symbol": ["A", "A"],
                "industry": ["科技", "科技"],
                "market_cap": [100.0, 101.0],
                "adv20": [2.0, 2.0],
                "forward_return": [0.01, 0.02],
            }
        )
        fundamentals = pd.DataFrame(
            {
                "symbol": ["A"], "industry": ["科技"],
                "report_period": pd.to_datetime(["2024-03-31"]),
                "announce_date": pd.to_datetime(["2024-04-30"]),
                "roe_ttm": [0.1], "cfo_to_assets": [0.05],
                "accruals_to_assets": [0.01], "revenue_growth": [0.08],
                "pe_ttm": [20.0], "pb": [2.0],
            }
        )
        result = align_fundamentals_asof(market, fundamentals)
        self.assertEqual(len(result), 1)
        self.assertEqual(result.iloc[0]["date"], pd.Timestamp("2024-05-01"))
        self.assertLessEqual(result.iloc[0]["announce_date"], result.iloc[0]["date"])


if __name__ == "__main__":
    unittest.main()

