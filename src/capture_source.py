"""Capture the fixed paired reports after metadata-only selection.

No errors, scores or actual-versus-forecast joins are computed here.
"""
from pathlib import Path
from datetime import datetime, date, time, timedelta, timezone
from io import BytesIO
from zipfile import ZipFile
import argparse
import gzip
import hashlib
import json
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]


def sha(content):
    return hashlib.sha256(content).hexdigest()


def write_json(path, value):
    path.write_bytes((json.dumps(value, indent=2, ensure_ascii=False) + "\n").encode())


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--discovery", required=True, type=Path)
    parser.add_argument("--raw-dir", required=True, type=Path)
    args = parser.parse_args()
    plan = json.loads((ROOT / "data/source_plan.json").read_bytes())
    assert plan["outcomes_retrieved"] is False
    assert not (ROOT / "data/documents.json").exists()
    args.raw_dir.mkdir(exist_ok=False)
    listings = {}
    for kind, filename in [("forecast", "report-list.json"), ("actual", "actual-list.json")]:
        native = (args.discovery / filename).read_bytes()
        docs = [item["Document"] for item in json.loads(native)["ListDocsByRptTypeRes"]["DocumentList"]]
        # Only fields needed to identify the public document and its publication assertion.
        listings[kind] = [{key: d[key] for key in ["DocID", "PublishDate", "ReportTypeID", "FriendlyName", "ConstructedName", "ContentSize", "SecurityStatus"]} for d in docs]
        assert all(d["SecurityStatus"] == "P" for d in listings[kind])
        write_json(ROOT / ("data/" + kind + "_listing.json"), dict(native_listing_sha256=sha(native), documents=listings[kind]))
    selected = []
    offset = timezone(timedelta(hours=-5))
    for text in plan["days"]:
        day = date.fromisoformat(text)
        cutoffs = {
            "day_ahead": datetime.combine(day - timedelta(days=1), time(12), offset),
            "same_day_noon": datetime.combine(day, time(12), offset),
            "end_of_day": datetime.combine(day, time(23, 59, 59), offset),
        }
        for policy, cutoff in cutoffs.items():
            candidates = [d for d in listings["forecast"] if d["FriendlyName"].endswith("_csv") and datetime.fromisoformat(d["PublishDate"]) <= cutoff]
            assert candidates, (text, policy, "no eligible document")
            latest = max(datetime.fromisoformat(d["PublishDate"]) for d in candidates)
            winners = [d for d in candidates if datetime.fromisoformat(d["PublishDate"]) == latest]
            assert len(winners) == 1, (text, policy, "publication tie")
            assert timedelta(0) <= cutoff - latest <= timedelta(minutes=plan["max_age_minutes"])
            csv_doc = winners[0]
            xml_docs = [d for d in listings["forecast"] if d["PublishDate"] == csv_doc["PublishDate"] and d["FriendlyName"].endswith("_xml")]
            assert len(xml_docs) == 1
            selected.append(dict(day=text, policy=policy, cutoff=cutoff.isoformat(), csv_id=csv_doc["DocID"], xml_id=xml_docs[0]["DocID"], published=csv_doc["PublishDate"], kind="forecast"))
        next_day = day + timedelta(days=1)
        actuals = [d for d in listings["actual"] if d["FriendlyName"].endswith("_csv") and datetime.fromisoformat(d["PublishDate"]).date() == next_day]
        assert actuals
        earliest = min(datetime.fromisoformat(d["PublishDate"]) for d in actuals)
        csv_docs = [d for d in actuals if datetime.fromisoformat(d["PublishDate"]) == earliest]
        assert len(csv_docs) == 1
        csv_doc = csv_docs[0]
        xml_docs = [d for d in listings["actual"] if d["PublishDate"] == csv_doc["PublishDate"] and d["FriendlyName"].endswith("_xml")]
        assert len(xml_docs) == 1
        selected.append(dict(day=text, kind="actual", csv_id=csv_doc["DocID"], xml_id=xml_docs[0]["DocID"], published=csv_doc["PublishDate"]))
    write_json(ROOT / "data/selection.json", selected)
    documents = []
    seen = set()
    for item in selected:
        for fmt in ["csv", "xml"]:
            doc_id = item[fmt + "_id"]
            if doc_id in seen:
                continue
            seen.add(doc_id)
            doc = next(d for d in listings[item["kind"]] if d["DocID"] == doc_id)
            url = "https://www.ercot.com/misdownload/servlets/mirDownload?doclookupId=" + doc_id
            with urlopen(Request(url, headers={"User-Agent": "Independent-load-forecast-audit/1.0"}), timeout=45) as response:
                assert response.status == 200
                raw = response.read()
            assert len(raw) == int(doc["ContentSize"]), doc_id
            (args.raw_dir / doc["ConstructedName"]).write_bytes(raw)
            with ZipFile(BytesIO(raw)) as z:
                names = z.namelist()
                assert len(names) == 1 and names[0].endswith("." + fmt)
                payload = z.read(names[0])
            rel = "data/native/" + doc_id + "." + fmt + ".gz"
            (ROOT / rel).parent.mkdir(exist_ok=True)
            (ROOT / rel).write_bytes(gzip.compress(payload, mtime=0))
            documents.append(dict(**doc, kind=item["kind"], format=fmt, url=url, archive_sha256=sha(raw), archive_bytes=len(raw), payload_member=names[0], payload_sha256=sha(payload), payload_bytes=len(payload), path=rel, compressed_sha256=sha((ROOT / rel).read_bytes()), retrieved_utc=datetime.now(timezone.utc).isoformat()))
            print("CAPTURED", item["kind"], fmt, doc_id, len(raw), flush=True)
    write_json(ROOT / "data/documents.json", documents)
    print(json.dumps(dict(status="SOURCE_CAPTURED_NOT_SCORED", documents=len(documents), selectors=len(selected), bytes=sum(x["archive_bytes"] for x in documents))))


if __name__ == "__main__":
    main()
