"""Project only the prespecified source cells without computing forecast errors."""

from pathlib import Path
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import csv
import gzip
import io
import json

ROOT = Path(__file__).resolve().parents[1]
ACTUAL_NAMES = dict(
    Coast="COAST",
    East="EAST",
    FarWest="FAR_WEST",
    North="NORTH",
    NorthCentral="NORTH_C",
    SouthCentral="SOUTH_C",
    Southern="SOUTHERN",
    West="WEST",
    SystemTotal="TOTAL",
)
OFFSET = timezone(timedelta(hours=-5))


def target_rows(rows, date_field, day):
    selected = [
        r
        for r in rows
        if datetime.strptime(r[date_field], "%m/%d/%Y").date().isoformat() == day
    ]
    assert len(selected) == 24, "incomplete target day"
    hours = set()
    for row in selected:
        hour, minute = row["HourEnding"].split(":")
        hour = int(hour)
        assert (
            minute == "00" and 1 <= hour <= 24 and row["DSTFlag"] == "N"
        ), "unsupported hour or DST flag"
        assert hour not in hours, "duplicate target hour"
        hours.add(hour)
    assert hours == set(range(1, 25))
    return selected


def native_load(value):
    number = Decimal(value)
    assert number.is_finite() and number >= 0, "invalid source load"
    return number


def project():
    plan = json.loads((ROOT / "data/source_plan.json").read_bytes())
    selections = json.loads((ROOT / "data/selection.json").read_bytes())
    docs = {
        d["DocID"]: d for d in json.loads((ROOT / "data/documents.json").read_bytes())
    }
    output = []
    for selection in selections:
        doc = docs[selection["csv_id"]]
        source_rows = list(
            csv.DictReader(
                io.StringIO(
                    gzip.decompress((ROOT / doc["path"]).read_bytes()).decode(
                        "utf-8-sig"
                    )
                )
            )
        )
        native_date = "DeliveryDate" if doc["kind"] == "forecast" else "OperDay"
        target = target_rows(source_rows, native_date, selection["day"])
        hours = set()
        for row in target:
            hour, minute = row["HourEnding"].split(":")
            hour = int(hour)
            assert minute == "00" and 1 <= hour <= 24 and row["DSTFlag"] == "N"
            assert hour not in hours
            hours.add(hour)
            start = datetime.fromisoformat(selection["day"]).replace(
                tzinfo=OFFSET
            ) + timedelta(hours=hour - 1)
            for zone in plan["zones"]:
                value = row[zone if doc["kind"] == "forecast" else ACTUAL_NAMES[zone]]
                native_load(value)
                output.append(
                    dict(
                        kind=doc["kind"],
                        day=selection["day"],
                        policy=selection.get("policy", "reference"),
                        hour_ending=hour,
                        dst_flag=row["DSTFlag"],
                        zone=zone,
                        load_mw=value,
                        doc_id=doc["DocID"],
                        published=doc["PublishDate"],
                        interval_start=start.isoformat(),
                        interval_end=(start + timedelta(hours=1)).isoformat(),
                    )
                )
        assert hours == set(range(1, 25))
    return sorted(
        output,
        key=lambda r: (r["day"], r["kind"], r["policy"], r["hour_ending"], r["zone"]),
    )


def main():
    rows = project()
    with (ROOT / "data/qualified.csv").open(
        "w", encoding="utf-8", newline=""
    ) as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    print("SOURCE_PROJECTION", len(rows), "rows; no forecast errors computed")


if __name__ == "__main__":
    main()
