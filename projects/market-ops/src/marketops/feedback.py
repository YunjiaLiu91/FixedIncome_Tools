"""A small requirements queue with explicit grouping and priority rules."""

from collections import defaultdict
import unicodedata
from .quotes import timestamp


def normalized(value):
    return " ".join(unicodedata.normalize("NFKC", value).split()).casefold()


def triage(rows, cutoff):
    cutoff = timestamp(cutoff)
    groups = defaultdict(list)
    ids = [r["ticket_id"].strip() for r in rows]
    if any(not value for value in ids) or len(set(ids)) != len(ids):
        raise ValueError("feedback ticket IDs must be nonempty and unique")
    for row in rows:
        submitted = timestamp(row["submitted_at"])
        if submitted > cutoff:
            continue
        impact, urgency = int(row["impact"]), int(row["urgency"])
        if impact not in {1, 2, 3} or urgency not in {1, 2, 3}:
            raise ValueError("impact and urgency must be integers from 1 to 3")
        if not row["module"].strip() or not row["title"].strip() or not row["acceptance"].strip():
            raise ValueError("module, title and acceptance are required")
        groups[(normalized(row["module"]), normalized(row["title"]))].append(row)
    queue = []
    for group in groups.values():
        group.sort(key=lambda r: (timestamp(r["submitted_at"]), r["ticket_id"]))
        lead = group[0]
        # Use the highest score of an actual ticket, not a synthetic combination across tickets.
        score = max(int(r["impact"]) + int(r["urgency"]) for r in group)
        priority = "P1" if score >= 5 else "P2" if score >= 3 else "P3"
        queue.append(dict(ticket_id=lead["ticket_id"], module=lead["module"], title=lead["title"],
                          priority=priority, score=score, related_tickets=";".join(r["ticket_id"] for r in group),
                          reports=len(group), roles=";".join(sorted({r["role"] for r in group})),
                          acceptance=" / ".join(dict.fromkeys(r["acceptance"] for r in group)),
                          evidence_ref=";".join(dict.fromkeys(r["evidence_ref"] for r in group)),
                          status="待复核"))
    return sorted(queue, key=lambda r: (r["priority"], -r["score"], r["ticket_id"]))
