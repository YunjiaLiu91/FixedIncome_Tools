from pathlib import Path
import tempfile
import unittest

from marketops.bonds import bond_check
from marketops.cli import read_csv, run
from marketops.feedback import triage
from marketops.quotes import clean_quotes, disposition_counts, instrument_map, overview
from marketops.sample import write_sample


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.inputs = self.root / "inputs"
        write_sample(self.inputs)
        self.instruments = instrument_map(read_csv(self.inputs / "instruments.csv"))
        self.raw = read_csv(self.inputs / "quotes.csv")
        self.cutoff = "2026-09-28T18:00:00+08:00"
        self.vendors = ["feed_a", "feed_b"]
        self.settings = dict(business_date="2026-09-28", vendor_priority=self.vendors,
                             bond_gap_bp=5.0, price_gap_pct=1.0)

    def tearDown(self):
        self.temp.cleanup()

    def clean(self, rows=None):
        return clean_quotes(self.raw if rows is None else rows, self.instruments, self.cutoff, self.vendors)

    def test_dispositions_reconcile_to_raw_count(self):
        quotes, decisions = self.clean()
        counts = disposition_counts(decisions)
        self.assertEqual(counts, dict(accepted=69, rejected=10, not_available=2, superseded=2))
        self.assertEqual(sum(counts.values()), len(self.raw))
        self.assertEqual(len(quotes), counts["accepted"])

    def test_yield_percent_and_decimal_are_normalized(self):
        bond = next(r for r in self.raw if r["instrument_id"] == "SIM_BOND_3")
        decimal = dict(bond, record_id="DEC", vendor="feed_b", quote_unit="yield_decimal",
                       **{k: str(float(bond[k]) / 100) for k in ("bid", "ask", "mid")})
        quotes, _ = self.clean([bond, decimal])
        self.assertAlmostEqual(quotes[0]["mid"], quotes[1]["mid"], places=12)
        self.assertEqual(quotes[0]["quote_unit"], "yield_decimal")

    def test_same_revision_in_equivalent_units_is_not_a_conflict(self):
        original = dict(self.raw[0], record_id="PCT", bid="2.050", mid="2.055", ask="2.060")
        decimal = dict(original, record_id="DEC", bid="0.02050", mid="0.02055", ask="0.02060", quote_unit="yield_decimal")
        quotes, decisions = self.clean([original, decimal])
        self.assertEqual(len(quotes), 1)
        self.assertEqual(disposition_counts(decisions)["superseded"], 1)
        self.assertFalse(any(d["reason"] == "CONFLICTING_REVISION" for d in decisions))

    def test_bond_quote_before_issue_is_quarantined(self):
        original = dict(self.raw[0], asof_date="2023-09-21")
        quotes, decisions = self.clean([original])
        self.assertEqual(quotes, [])
        self.assertIn("BEFORE_ISSUE", decisions[0]["reason"])

    def test_late_arrival_and_future_publication_are_excluded(self):
        quotes, decisions = self.clean()
        self.assertFalse({"LATE001", "FUTURE001"} & {q["record_id"] for q in quotes})
        for d in decisions:
            if d["record_id"] in {"LATE001", "FUTURE001"}:
                self.assertEqual(d["disposition"], "not_available")

    def test_equivalent_utc_timestamp_has_same_business_day(self):
        original = dict(self.raw[0], record_id="LOCAL", asof_date="2026-09-28",
                        published_at="2026-09-28T00:10:00+08:00", ingested_at="2026-09-28T00:12:00+08:00")
        utc = dict(original, published_at="2026-09-27T16:10:00+00:00", ingested_at="2026-09-27T16:12:00+00:00")
        quotes, decisions = self.clean([utc])
        self.assertEqual(len(quotes), 1)
        self.assertEqual(decisions[0]["reason"], "OK")

    def test_invalid_numbers_spreads_units_and_timezone_are_quarantined(self):
        _, decisions = self.clean()
        expected = {"ERR_NUMBER": "BAD_NUMBER", "ERR_CROSS": "CROSSED_QUOTE", "ERR_MID": "MID_OUTSIDE_SPREAD",
                    "ERR_VOLUME": "BAD_VOLUME", "ERR_UNIT": "BAD_UNIT", "ERR_TZ": "BAD_DATE_OR_TIMEZONE", "ERR_TIME": "TIME_SEQUENCE"}
        by_id = {d["record_id"]: d for d in decisions}
        for record, reason in expected.items():
            with self.subTest(record=record):
                self.assertEqual(by_id[record]["disposition"], "rejected")
                self.assertIn(reason, by_id[record]["reason"])

    def test_latest_correction_and_exact_retransmission(self):
        quotes, decisions = self.clean()
        chosen = next(q for q in quotes if q["instrument_id"] == "SIM_BOND_3" and q["asof_date"] == "2026-09-28" and q["vendor"] == "feed_a")
        self.assertEqual(chosen["record_id"], "REV001")
        self.assertAlmostEqual(chosen["mid"], 0.02055)
        self.assertEqual(next(d for d in decisions if d["record_id"] == "REV002")["reason"], "DUPLICATE")

    def test_conflicting_latest_revision_does_not_fall_back_silently(self):
        original = dict(self.raw[0], record_id="OLD")
        latest = dict(original, record_id="NEW1", published_at="2026-09-21T17:00:00+08:00", ingested_at="2026-09-21T17:01:00+08:00")
        conflict = dict(latest, record_id="NEW2", bid="2.200", mid="2.205", ask="2.210")
        quotes, decisions = self.clean([original, latest, conflict])
        self.assertEqual(quotes, [])
        self.assertTrue(all(d["reason"] == "CONFLICTING_REVISION" for d in decisions))

    def test_cutoff_prevents_using_later_valid_correction(self):
        original = dict(self.raw[0], record_id="OLD")
        later = dict(original, record_id="LATER", published_at="2026-09-28T18:01:00+08:00", ingested_at="2026-09-28T18:02:00+08:00", bid="2.200", mid="2.205", ask="2.210")
        quotes, _ = self.clean([original, later])
        self.assertEqual([q["record_id"] for q in quotes], ["OLD"])

    def test_duplicate_record_ids_stop_the_run(self):
        with self.assertRaisesRegex(ValueError, "record_id"):
            self.clean([self.raw[0], self.raw[0]])

    def test_reordering_input_does_not_change_selected_values(self):
        first, _ = self.clean()
        reverse, _ = self.clean(list(reversed(self.raw)))
        fields = ("record_id", "instrument_id", "asof_date", "vendor", "mid")
        self.assertEqual([tuple(q[k] for k in fields) for q in first], [tuple(q[k] for k in fields) for q in reverse])

    def test_stale_snapshot_retains_original_date(self):
        quotes, _ = self.clean()
        snapshots, findings, movements = overview(quotes, self.instruments, self.settings)
        stale = next(q for q in snapshots if q["instrument_id"] == "SIM_T")
        self.assertEqual(stale["asof_date"], "2026-09-25")
        self.assertEqual(stale["age_days"], 3)
        self.assertTrue(any(f["code"] == "STALE" for f in findings))
        self.assertEqual(next(m for m in movements if m["instrument_id"] == "SIM_T")["end_date"], "2026-09-25")

    def test_source_gap_uses_basis_points_and_same_date(self):
        quotes, _ = self.clean()
        _, findings, _ = overview(quotes, self.instruments, self.settings)
        gap = next(f for f in findings if f["code"] == "SOURCE_GAP")
        self.assertEqual(gap["instrument_id"], "SIM_BOND_10")
        self.assertIn("19.00bp", gap["detail"])

    def test_feedback_preserves_both_acceptance_conditions(self):
        queue = triage(read_csv(self.inputs / "feedback.csv"), self.cutoff)
        self.assertEqual(len(queue), 4)
        first = next(q for q in queue if q["ticket_id"] == "REQ001")
        self.assertEqual(first["priority"], "P1")
        self.assertEqual(first["related_tickets"], "REQ001;REQ002")
        self.assertIn("导出表明确", first["acceptance"])

    def test_feedback_priority_does_not_combine_different_tickets(self):
        original = read_csv(self.inputs / "feedback.csv")[0]
        group = [dict(original, impact=3, urgency=1), dict(original, ticket_id="SECOND", impact=1, urgency=3)]
        queue = triage(group, self.cutoff)
        self.assertEqual(queue[0]["score"], 4)
        self.assertEqual(queue[0]["priority"], "P2")

    def test_future_feedback_is_not_in_current_queue(self):
        row = dict(read_csv(self.inputs / "feedback.csv")[0], submitted_at="2026-09-29T10:00:00+08:00")
        self.assertEqual(triage([row], self.cutoff), [])

    def test_coupon_date_par_bond_matches_independent_pv(self):
        result = bond_check(self.instruments["SIM_BOND_3"], 0.03, "2026-09-28")
        self.assertAlmostEqual(result["clean_price"], 100.0, places=9)
        self.assertEqual(result["accrued_interest"], 0.0)
        self.assertAlmostEqual(result["pv_difference"], 0.0, places=9)

    def test_off_coupon_price_and_dv01(self):
        instrument = self.instruments["SIM_BOND_10"]
        result = bond_check(instrument, 0.0263, "2026-09-28")
        self.assertGreater(result["accrued_interest"], 0)
        self.assertAlmostEqual(result["dirty_price"], result["clean_price"] + result["accrued_interest"], places=12)
        self.assertAlmostEqual(result["pv_difference"], 0.0, places=8)
        up, down = (bond_check(instrument, y, "2026-09-28") for y in (0.0264, 0.0262))
        self.assertLess(up["clean_price"], result["clean_price"])
        self.assertAlmostEqual(result["dv01_per_100"], (down["clean_price"] - up["clean_price"]) / 2, places=10)
        self.assertGreater(result["modified_duration"], 0)

    def test_maturity_is_not_priceable(self):
        with self.assertRaisesRegex(ValueError, "settlement"):
            bond_check(self.instruments["SIM_BOND_3"], 0.03, "2029-09-28")

    def test_repeat_runs_produce_identical_outputs(self):
        first, second = self.root / "first", self.root / "second"
        a, b = run(self.inputs, first), run(self.inputs, second)
        self.assertEqual(a, b)
        for file in first.iterdir():
            self.assertEqual(file.read_bytes(), (second / file.name).read_bytes(), file.name)
        self.assertEqual(a["latest_coverage"], 5)
        self.assertEqual(a["requirement_groups"], 4)


if __name__ == "__main__":
    unittest.main()
