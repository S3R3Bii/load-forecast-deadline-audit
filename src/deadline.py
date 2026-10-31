"""Select by an aware publication deadline, never by forecast accuracy."""
from datetime import datetime
from pathlib import Path
import argparse
import json


def aware(value):
    stamp = datetime.fromisoformat(value)
    if stamp.utcoffset() is None:
        raise ValueError("An explicit timestamp offset is required")
    return stamp


def select(reports, deadline, max_age_minutes=90):
    cutoff = aware(deadline)
    if max_age_minutes < 0:
        raise ValueError("Maximum age must be nonnegative")
    rows = [(r, aware(r["PublishDate"])) for r in reports]
    if len({r["DocID"] for r, _ in rows}) != len(rows):
        return dict(status="UNAVAILABLE", reason="duplicate document identity")
    eligible = [(r, stamp) for r, stamp in rows if stamp <= cutoff]
    if not eligible:
        return dict(status="UNAVAILABLE", reason="no document before deadline")
    latest = max(stamp for _, stamp in eligible)
    winners = [r for r, stamp in eligible if stamp == latest]
    if len(winners) != 1:
        return dict(status="UNAVAILABLE", reason="ambiguous publication tie")
    age = (cutoff - latest).total_seconds()
    if age > max_age_minutes * 60:
        return dict(status="UNAVAILABLE", reason="latest eligible document is stale")
    return dict(status="SELECTED", doc_id=winners[0]["DocID"], published=winners[0]["PublishDate"], deadline=deadline, age_seconds=int(age))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--deadline", required=True, help="ISO8601 with explicit offset")
    parser.add_argument("--reports", type=Path, default=Path(__file__).resolve().parents[1] / "data/forecast_listing.json")
    parser.add_argument("--max-age-minutes", type=int, default=90)
    args = parser.parse_args()
    reports = json.loads(args.reports.read_bytes())
    if isinstance(reports, dict):
        reports = reports["documents"]
    reports = [r for r in reports if "FriendlyName" not in r or r["FriendlyName"].endswith("_csv")]
    try:
        result = select(reports, args.deadline, args.max_age_minutes)
    except (ValueError, KeyError) as error:
        result = dict(status="UNAVAILABLE", reason=str(error))
    print(json.dumps(result, indent=2))
    return 0 if result["status"] == "SELECTED" else 2


if __name__ == "__main__":
    raise SystemExit(main())
