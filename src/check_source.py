"""Independently bind paired native payloads, SQLite selectors and source cells.

This checker imports no production reader or selector.
"""

from pathlib import Path
from datetime import datetime, timedelta
from decimal import Decimal
from fractions import Fraction
import csv
import gzip
import hashlib
import io
import json
import sqlite3
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
CHECKS = 0


def require(condition, detail):
    global CHECKS
    CHECKS += 1
    assert condition, detail


def main():
    plan = json.loads((ROOT / "data/source_plan.json").read_bytes())
    documents = json.loads((ROOT / "data/documents.json").read_bytes())
    docs = {d["DocID"]: d for d in documents}
    selections = json.loads((ROOT / "data/selection.json").read_bytes())
    db = sqlite3.connect(":memory:")
    db.execute("create table reports(kind, id, published, fmt, epoch integer)")
    for kind in ["forecast", "actual"]:
        listing = json.loads((ROOT / ("data/" + kind + "_listing.json")).read_bytes())[
            "documents"
        ]
        require(
            len({x["DocID"] for x in listing}) == len(listing),
            kind + " list identities",
        )
        for doc in listing:
            when = datetime.fromisoformat(doc["PublishDate"])
            require(when.utcoffset() is not None, "aware publication")
            fmt = doc["FriendlyName"].rsplit("_", 1)[-1]
            db.execute(
                "insert into reports values(?,?,?,?,?)",
                (kind, doc["DocID"], doc["PublishDate"], fmt, int(when.timestamp())),
            )
    native = {}
    source_rows = 0
    for doc in documents:
        content = (ROOT / doc["path"]).read_bytes()
        require(
            hashlib.sha256(content).hexdigest() == doc["compressed_sha256"],
            "compressed bytes",
        )
        payload = gzip.decompress(content)
        require(
            hashlib.sha256(payload).hexdigest() == doc["payload_sha256"]
            and len(payload) == doc["payload_bytes"],
            "payload bytes",
        )
        if doc["format"] == "csv":
            rows = list(csv.DictReader(io.StringIO(payload.decode("utf-8-sig"))))
            source_rows += len(rows)
        else:
            tree = ET.fromstring(payload)
            rows = [
                {field.tag.rsplit("}", 1)[-1]: field.text for field in row}
                for row in tree
            ]
        require(bool(rows), "nonempty source")
        keydate = "DeliveryDate" if doc["kind"] == "forecast" else "OperDay"
        keyed = {}
        for row in rows:
            key = (row[keydate], int(row["HourEnding"].split(":")[0]), row["DSTFlag"])
            require(key not in keyed, ("native duplicate", doc["DocID"], key))
            require(row["HourEnding"].split(":")[1] == "00", "hour granularity")
            keyed[key] = row
        native[doc["DocID"]] = keyed
    mapping = dict(
        zip(
            plan["zones"],
            [
                "COAST",
                "EAST",
                "FAR_WEST",
                "NORTH",
                "NORTH_C",
                "SOUTH_C",
                "SOUTHERN",
                "WEST",
                "TOTAL",
            ],
        )
    )
    expected = []
    for sel in selections:
        csv_doc, xml_doc = docs[sel["csv_id"]], docs[sel["xml_id"]]
        require(
            csv_doc["PublishDate"] == xml_doc["PublishDate"] == sel["published"],
            "pair publication",
        )
        kind = sel["kind"]
        require(csv_doc["kind"] == xml_doc["kind"] == kind, "pair role")
        require(set(native[sel["csv_id"]]) == set(native[sel["xml_id"]]), "native keys")
        for key, row in native[sel["csv_id"]].items():
            other = native[sel["xml_id"]][key]
            require(set(row) == set(other), "native fields")
            for field in row:
                if field in ["DeliveryDate", "OperDay", "DSTFlag"]:
                    require(row[field] == other[field], "native text")
                elif field == "HourEnding":
                    require(
                        int(row[field].split(":")[0])
                        == int(other[field].split(":")[0]),
                        "native hour",
                    )
                else:
                    require(
                        Fraction(row[field]) == Fraction(other[field]), "native numeric"
                    )
        if kind == "forecast":
            cutoff = datetime.fromisoformat(sel["cutoff"])
            winners = db.execute(
                "select id,published,epoch from reports where kind='forecast' and fmt='csv' and epoch=(select max(epoch) from reports where kind='forecast' and fmt='csv' and epoch<=?)",
                (int(cutoff.timestamp()),),
            ).fetchall()
            require(
                len(winners) == 1 and winners[0][0] == sel["csv_id"],
                "SQL as-of selector",
            )
            require(
                0 <= cutoff.timestamp() - winners[0][2] <= plan["max_age_minutes"] * 60,
                "freshness",
            )
            pair = db.execute(
                "select id from reports where kind='forecast' and fmt='xml' and epoch=?",
                (winners[0][2],),
            ).fetchall()
            require(pair == [(sel["xml_id"],)], "SQL pair uniqueness")
        else:
            next_day = (
                (datetime.fromisoformat(sel["day"]) + timedelta(days=1))
                .date()
                .isoformat()
            )
            pairs = db.execute(
                "select id from reports where kind='actual' and fmt='csv' and substr(published,1,10)=? and epoch=(select min(epoch) from reports where kind='actual' and fmt='csv' and substr(published,1,10)=?)",
                (next_day, next_day),
            ).fetchall()
            require(pairs == [(sel["csv_id"],)], "SQL actual selector")
        day_rows = {
            key: row
            for key, row in native[sel["csv_id"]].items()
            if datetime.strptime(key[0], "%m/%d/%Y").date().isoformat() == sel["day"]
        }
        require(
            len(day_rows) == 24 and {k[1] for k in day_rows} == set(range(1, 25)),
            "complete day",
        )
        for (_, hour, flag), row in day_rows.items():
            require(flag == "N", "cohort excludes ambiguous repeated hour")
            start = datetime.fromisoformat(sel["day"] + "T00:00:00-05:00") + timedelta(
                hours=hour - 1
            )
            for zone in plan["zones"]:
                value = row[zone if kind == "forecast" else mapping[zone]]
                require(
                    Decimal(value).is_finite() and Fraction(value) >= 0,
                    "finite nonnegative source",
                )
                expected.append(
                    dict(
                        kind=kind,
                        day=sel["day"],
                        policy=sel.get("policy", "reference"),
                        hour_ending=str(hour),
                        dst_flag=flag,
                        zone=zone,
                        load_mw=value,
                        doc_id=sel["csv_id"],
                        published=sel["published"],
                        interval_start=start.isoformat(),
                        interval_end=(start + timedelta(hours=1)).isoformat(),
                    )
                )
    actual = list(
        csv.DictReader((ROOT / "data/qualified.csv").open(encoding="utf-8", newline=""))
    )
    order = lambda r: (
        r["day"],
        r["kind"],
        r["policy"],
        int(r["hour_ending"]),
        r["zone"],
    )
    expected.sort(key=order)
    require(len(actual) == len(expected) == 4320, "projection cardinality")
    for left, right in zip(actual, expected):
        for field in right:
            require(left[field] == right[field], ("projected source cell", field))
    result = dict(
        status="PASS_SOURCE_ONLY",
        conditions=CHECKS,
        native_csv_rows=source_rows,
        native_documents=len(documents),
        selector_records=len(selections),
        projected_rows=len(actual),
        no_error_scores_computed=True,
        input_sha256={
            str(p.relative_to(ROOT))
            .replace("\\", "/"): hashlib.sha256(p.read_bytes())
            .hexdigest()
            for p in sorted((ROOT / "data").rglob("*"))
            if p.is_file() and p.name != "source_verification.json"
        },
    )
    (ROOT / "data/source_verification.json").write_bytes(
        (json.dumps(result, indent=2) + "\n").encode()
    )
    print(json.dumps({k: v for k, v in result.items() if k != "input_sha256"}))


if __name__ == "__main__":
    main()
