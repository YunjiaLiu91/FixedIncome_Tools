"""Run from a supplied input directory or generate the fixed sample."""

import argparse
import csv
from datetime import date
import hashlib
import json
from pathlib import Path
from urllib.parse import urlparse
import QuantLib as ql

from .bonds import bond_check
from .feedback import triage
from .quotes import clean_quotes, disposition_counts, instrument_map, number, overview, timestamp
from .report import brief_text, html_report
from .sample import write_csv, write_sample


def read_csv(path):
    with Path(path).open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def run(inputs, output):
    inputs, output = Path(inputs), Path(output)
    if inputs.resolve() == output.resolve():
        raise ValueError("output must be different from input")
    settings = json.loads((inputs / "settings.json").read_text(encoding="utf-8"))
    cutoff = timestamp(settings["cutoff"])
    if cutoff.date() != date.fromisoformat(settings["business_date"]):
        raise ValueError("cutoff and business date must agree")
    vendors = settings["vendor_priority"]
    if not vendors or len(set(vendors)) != len(vendors):
        raise ValueError("vendor priority must be nonempty and unique")
    if number(settings["bond_gap_bp"]) < 0 or number(settings["price_gap_pct"]) < 0:
        raise ValueError("source gap thresholds cannot be negative")
    instruments = instrument_map(read_csv(inputs / "instruments.csv"))
    raw = read_csv(inputs / "quotes.csv")
    quotes, decisions = clean_quotes(raw, instruments, settings["cutoff"], vendors)
    snapshots, findings, movements = overview(quotes, instruments, settings)
    feedback = read_csv(inputs / "feedback.csv")
    queue = triage(feedback, settings["cutoff"])
    sources = read_csv(inputs / "sources.csv")
    review_date = date.fromisoformat(settings["source_review_date"])
    for s in sources:
        if urlparse(s["url"]).scheme != "https" or not urlparse(s["url"]).netloc:
            raise ValueError("source links must use https")
        if date.fromisoformat(s["observed_on"]) > review_date:
            raise ValueError("source observations cannot be after the review date")
    bonds = []
    for quote in snapshots:
        if quote["asset_class"] == "bond":
            # Missing current quotes are reported, not priced with yesterday's yield.
            if quote["age_days"]:
                continue
            bonds.append(bond_check(instruments[quote["instrument_id"]], quote["mid"], settings["business_date"]))
    result = dict(settings=settings, raw_rows=len(raw), counts=disposition_counts(decisions),
                  snapshots=snapshots, findings=findings, movements=movements, decisions=decisions,
                  bonds=bonds, feedback_rows=sum(timestamp(r["submitted_at"]) <= cutoff for r in feedback),
                  queue=queue, sources=sources)
    output.mkdir(parents=True, exist_ok=True)
    exports = {
        "clean_quotes.csv": (quotes, ["record_id", "instrument_id", "name", "asset_class", "asof_date", "vendor", "published_at", "ingested_at", "bid", "ask", "mid", "volume", "quote_unit", "source_line"]),
        "decisions.csv": (decisions, list(raw[0]) + ["source_line", "disposition", "reason", "standard_unit"] if raw else ["record_id", "disposition", "reason"]),
        "source_findings.csv": (findings, ["instrument_id", "code", "detail"]),
        "market_changes.csv": (movements, ["instrument_id", "name", "vendor", "start_date", "end_date", "change", "unit", "status"]),
        "requirements.csv": (queue, ["ticket_id", "module", "title", "priority", "score", "related_tickets", "reports", "roles", "acceptance", "evidence_ref", "status"]),
        "bond_checks.csv": (bonds, ["instrument_id", "settlement_date", "yield_decimal", "clean_price", "accrued_interest", "dirty_price", "modified_duration", "dv01_per_100", "independent_dirty_price", "pv_difference", "quantlib_version"]),
    }
    for name, (rows, fields) in exports.items():
        write_csv(output / name, rows, fields)
    summary = {key: result[key] for key in ("settings", "raw_rows", "counts", "findings", "bonds", "feedback_rows")}
    summary["requirement_groups"] = len(queue)
    summary["instrument_count"] = len(instruments)
    summary["latest_coverage"] = sum(q["age_days"] == 0 for q in snapshots)
    (output / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (output / "brief.md").write_text(brief_text(result), encoding="utf-8")
    (output / "report.html").write_text(html_report(result), encoding="utf-8")
    manifest = dict(settings=settings, quantlib_version=ql.__version__,
                    input_sha256={name: hashlib.sha256((inputs / name).read_bytes()).hexdigest()
                                  for name in ("instruments.csv", "quotes.csv", "feedback.csv", "sources.csv", "settings.json")})
    (output / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return summary


def main(argv=None):
    parser = argparse.ArgumentParser(description="Market data checks and an operations brief")
    commands = parser.add_subparsers(dest="command", required=True)
    demo = commands.add_parser("demo", help="Generate and run a deliberately imperfect sample")
    demo.add_argument("--output", type=Path, default=Path("outputs/demo"))
    check = commands.add_parser("run", help="Run five supplied input files")
    check.add_argument("--input", type=Path, required=True)
    check.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    inputs = args.input if args.command == "run" else args.output / "inputs"
    if args.command == "demo":
        write_sample(inputs)
    try:
        summary = run(inputs, args.output)
    except (ValueError, KeyError, OSError) as exc:
        parser.exit(2, f"Input error: {exc}\n")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
