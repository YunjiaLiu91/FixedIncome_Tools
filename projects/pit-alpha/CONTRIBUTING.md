# Reproducing and extending the study

Every factor change should start with a short hypothesis: economic mechanism, data availability time, expected sign, holding period and a condition that would falsify the idea. Keep factor definitions fixed before inspecting the out-of-sample period.

Before submitting a change, run:

```bash
python -m unittest discover -s tests -v
fundamental-alpha demo --output outputs/demo
```

A pull request that changes factor behavior should include before/after IC, yearly stability, quantile monotonicity, turnover, decay and residual style exposures. A higher Sharpe alone is not sufficient evidence.

