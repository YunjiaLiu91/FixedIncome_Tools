"""Keep raw rows separate from accepted, point-in-time quotes."""

from collections import Counter, defaultdict
from datetime import date, datetime
import math


ASSET_UNITS = {"bond": {"yield_pct", "yield_decimal"}, "equity": {"cny"}, "future": {"points"}}
QUOTE_FIELDS = {"record_id", "instrument_id", "asof_date", "vendor", "published_at",
                "ingested_at", "bid", "ask", "mid", "volume", "quote_unit"}


def timestamp(value):
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("timestamps must include a timezone")
    return parsed


def number(value):
    result = float(value)
    if not math.isfinite(result):
        raise ValueError("non-finite number")
    return result


def instrument_map(rows):
    result = {}
    for row in rows:
        symbol = row["instrument_id"].strip()
        if not symbol or symbol in result:
            raise ValueError("instrument IDs must be nonempty and unique")
        if row["asset_class"] not in ASSET_UNITS or row["currency"] != "CNY":
            raise ValueError("demo supports CNY bond, equity and future instruments")
        if row["asset_class"] == "bond":
            issue, maturity = date.fromisoformat(row["issue_date"]), date.fromisoformat(row["maturity_date"])
            if issue >= maturity or int(row["frequency"]) not in {1, 2, 4}:
                raise ValueError("invalid bond schedule")
            if not 0 <= number(row["coupon_pct"]) <= 30:
                raise ValueError("invalid coupon")
        if row["asset_class"] == "future":
            date.fromisoformat(row["maturity_date"])
        result[symbol] = dict(row)
    if not result:
        raise ValueError("empty instrument master")
    return result


def clean_quotes(rows, instruments, cutoff, vendors):
    """Every row receives exactly one disposition. Unknown/conflicting rows never enter prices."""
    cutoff = timestamp(cutoff)
    ids = [r.get("record_id", "").strip() for r in rows]
    if any(not value for value in ids) or len(set(ids)) != len(ids):
        raise ValueError("record_id must be nonempty and unique; fix the source file")
    decisions, candidates = [], defaultdict(list)
    for line, raw in enumerate(rows, start=2):
        if not QUOTE_FIELDS.issubset(raw):
            raise ValueError("quote file is missing required columns")
        decision = dict(raw, source_line=line, disposition="rejected", reason="", standard_unit="")
        decisions.append(decision)
        reasons = []
        asof = None
        symbol, vendor = raw["instrument_id"].strip(), raw["vendor"].strip()
        instrument = instruments.get(symbol)
        if instrument is None:
            reasons.append("UNKNOWN_INSTRUMENT")
        if vendor not in vendors:
            reasons.append("UNKNOWN_VENDOR")
        try:
            asof = date.fromisoformat(raw["asof_date"])
            published, ingested = timestamp(raw["published_at"]), timestamp(raw["ingested_at"])
            if (published > ingested or published.astimezone(cutoff.tzinfo).date() < asof
                    or ingested.astimezone(cutoff.tzinfo).date() < asof):
                reasons.append("TIME_SEQUENCE")
            if asof > cutoff.date() or published > cutoff or ingested > cutoff:
                if not reasons:
                    decision.update(disposition="not_available", reason="AFTER_CUTOFF")
                    continue
                reasons.append("AFTER_CUTOFF")
        except (ValueError, TypeError):
            reasons.append("BAD_DATE_OR_TIMEZONE")
        try:
            bid, ask, mid, volume = [number(raw[k]) for k in ("bid", "ask", "mid", "volume")]
            if volume < 0 or volume != int(volume):
                reasons.append("BAD_VOLUME")
            if instrument is not None:
                asset = instrument["asset_class"]
                unit = raw["quote_unit"]
                if unit not in ASSET_UNITS[asset]:
                    reasons.append("BAD_UNIT")
                else:
                    scale = 0.01 if unit == "yield_pct" else 1.0
                    bid, ask, mid = (round(x * scale, 12) for x in (bid, ask, mid))
                    decision["standard_unit"] = "yield_decimal" if asset == "bond" else unit
                    if asset == "bond":
                        if any(not -0.02 <= x <= 0.30 for x in (bid, ask, mid)):
                            reasons.append("YIELD_RANGE")
                    elif min(bid, ask, mid) <= 0:
                        reasons.append("NONPOSITIVE_PRICE")
                    if bid > ask:
                        reasons.append("CROSSED_QUOTE")
                    if not bid - 1e-12 <= mid <= ask + 1e-12:
                        reasons.append("MID_OUTSIDE_SPREAD")
                    if (asof is not None and asset in {"bond", "future"}
                            and asof >= date.fromisoformat(instrument["maturity_date"])):
                        reasons.append("MATURED_INSTRUMENT")
                    if (asof is not None and asset == "bond"
                            and asof < date.fromisoformat(instrument["issue_date"])):
                        reasons.append("BEFORE_ISSUE")
        except (ValueError, TypeError):
            reasons.append("BAD_NUMBER")
        if reasons:
            decision["reason"] = ";".join(dict.fromkeys(reasons))
            continue
        normalized = dict(raw, instrument_id=symbol, vendor=vendor, bid=bid, ask=ask, mid=mid,
                          volume=int(volume), quote_unit=decision["standard_unit"], source_line=line,
                          asset_class=instrument["asset_class"], name=instrument["name"])
        candidates[(symbol, asof.isoformat(), vendor)].append((normalized, decision, published, ingested))

    accepted = []
    for group in candidates.values():
        latest = max((p, i) for _, _, p, i in group)
        contenders = [entry for entry in group if entry[2:] == latest]
        payloads = {(q["bid"], q["ask"], q["mid"], q["volume"], q["quote_unit"]) for q, _, _, _ in contenders}
        if len(payloads) > 1:
            for _, d, _, _ in group:
                d.update(disposition="rejected", reason="CONFLICTING_REVISION")
            continue
        winner = min(contenders, key=lambda entry: entry[0]["record_id"])
        for entry in group:
            q, d, _, _ = entry
            if entry is winner:
                d.update(disposition="accepted", reason="OK")
                accepted.append(q)
            else:
                d.update(disposition="superseded", reason="DUPLICATE" if entry[2:] == latest else "EARLIER_REVISION")
    accepted.sort(key=lambda q: (q["asof_date"], q["instrument_id"], vendors.index(q["vendor"])))
    return accepted, decisions


def overview(quotes, instruments, settings):
    """Choose a configured source; compare same-date sources without averaging them."""
    business_date = date.fromisoformat(settings["business_date"])
    priorities = settings["vendor_priority"]
    by_symbol = defaultdict(list)
    for q in quotes:
        by_symbol[q["instrument_id"]].append(q)
    snapshots, findings, movements = [], [], []
    for symbol, instrument in instruments.items():
        available = by_symbol[symbol]
        if not available:
            findings.append(dict(instrument_id=symbol, code="MISSING", detail="无可用行情"))
            continue
        latest_date = max(q["asof_date"] for q in available)
        latest = [q for q in available if q["asof_date"] == latest_date]
        selected = min(latest, key=lambda q: priorities.index(q["vendor"]))
        snapshot = dict(selected, age_days=(business_date - date.fromisoformat(latest_date)).days)
        snapshots.append(snapshot)
        if latest_date != business_date.isoformat():
            findings.append(dict(instrument_id=symbol, code="STALE", detail=f"最新日期 {latest_date}，未补值"))
        if selected["vendor"] != priorities[0]:
            findings.append(dict(instrument_id=symbol, code="SECONDARY_SOURCE", detail=f"使用 {selected['vendor']}"))
        for other in latest:
            if other["vendor"] == selected["vendor"]:
                continue
            if instrument["asset_class"] == "bond":
                gap = abs(selected["mid"] - other["mid"]) * 10000
                limit, unit = settings["bond_gap_bp"], "bp"
            else:
                gap = abs(other["mid"] / selected["mid"] - 1) * 100
                limit, unit = settings["price_gap_pct"], "%"
            if gap > limit + 1e-9:
                findings.append(dict(instrument_id=symbol, code="SOURCE_GAP",
                                     detail=f"{selected['vendor']} / {other['vendor']} 差 {gap:.2f}{unit}，阈值 {limit}{unit}"))
        # A consistent source and unfilled start/end dates are required for a market movement.
        history = sorted([q for q in available if q["vendor"] == selected["vendor"]], key=lambda q: q["asof_date"])
        if len(history) >= 2:
            first, last = history[0], history[-1]
            delta = (last["mid"] - first["mid"]) * 10000 if instrument["asset_class"] == "bond" else (last["mid"] / first["mid"] - 1) * 100
            movements.append(dict(instrument_id=symbol, name=instrument["name"], vendor=selected["vendor"],
                                  start_date=first["asof_date"], end_date=last["asof_date"], change=delta,
                                  unit="bp" if instrument["asset_class"] == "bond" else "%", status="stale" if snapshot["age_days"] else "current"))
    return snapshots, findings, movements


def disposition_counts(decisions):
    counts = Counter(d["disposition"] for d in decisions)
    return {key: counts[key] for key in ("accepted", "rejected", "not_available", "superseded")}
