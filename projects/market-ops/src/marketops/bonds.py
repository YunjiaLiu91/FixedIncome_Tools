"""Explicit demo conventions, with a one-basis-point parallel yield bump."""

from datetime import date
import QuantLib as ql


def qdate(value):
    parsed = date.fromisoformat(value)
    return ql.Date(parsed.day, parsed.month, parsed.year)


def bond_check(instrument, annual_yield, settlement_date):
    """Prices and DV01 are per 100 face; no trade/settlement calendar is implied."""
    settlement = qdate(settlement_date)
    issue, maturity = qdate(instrument["issue_date"]), qdate(instrument["maturity_date"])
    if not issue <= settlement < maturity:
        raise ValueError("settlement must be between issue and maturity")
    frequency = {1: ql.Annual, 2: ql.Semiannual, 4: ql.Quarterly}[int(instrument["frequency"])]
    # Dates are unadjusted with a NullCalendar so the illustrative terms are reproducible.
    schedule = ql.Schedule(issue, maturity, ql.Period(frequency), ql.NullCalendar(),
                           ql.Unadjusted, ql.Unadjusted, ql.DateGeneration.Backward, False)
    day_count = ql.ActualActual(ql.ActualActual.Bond, schedule)
    bond = ql.FixedRateBond(0, 100.0, schedule, [float(instrument["coupon_pct"]) / 100],
                            day_count, ql.Unadjusted, 100.0, issue)
    rate = float(annual_yield)
    if not -0.02 <= rate <= 0.30:
        raise ValueError("yield outside demo range")

    def clean(y):
        return ql.BondFunctions.cleanPrice(bond, y, day_count, ql.Compounded, frequency, settlement)

    price = clean(rate)
    accrued = bond.accruedAmount(settlement)
    dirty = price + accrued
    dv01 = (clean(rate - 0.0001) - clean(rate + 0.0001)) / 2
    duration = ql.BondFunctions.duration(bond, rate, day_count, ql.Compounded, frequency,
                                         ql.Duration.Modified, settlement)
    # Independent PV from the exposed cash flows on regular coupon periods.
    cashflows = [(cf.date(), cf.amount()) for cf in bond.cashflows() if cf.date() > settlement]
    manual_dirty = sum(amount / (1 + rate / int(instrument["frequency"])) **
                       (int(instrument["frequency"]) * day_count.yearFraction(settlement, payment))
                       for payment, amount in cashflows)
    return dict(instrument_id=instrument["instrument_id"], settlement_date=settlement_date,
                yield_decimal=rate, clean_price=price, accrued_interest=accrued, dirty_price=dirty,
                modified_duration=duration, dv01_per_100=dv01, independent_dirty_price=manual_dirty,
                pv_difference=dirty - manual_dirty, quantlib_version=ql.__version__)
