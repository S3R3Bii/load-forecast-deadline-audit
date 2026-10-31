"""One real deadline and authored unavailable-input exercises."""
from pathlib import Path
import argparse
import json
from deadline import select
ROOT=Path(__file__).resolve().parents[1]


def execute(out):
    docs=json.loads((ROOT/"data/forecast_listing.json").read_bytes())["documents"]
    docs=[d for d in docs if d["FriendlyName"].endswith("_csv")]
    deadline="2026-10-24T12:00:00-05:00"
    real=select(docs,deadline)
    source=next(x for x in json.loads((ROOT/"data/selection.json").read_bytes()) if x.get("policy")=="day_ahead" and x["day"]=="2026-10-25")
    assert real["status"]=="SELECTED" and real["doc_id"]==source["csv_id"]
    late=[dict(DocID="authored-late",PublishDate="2026-10-24T12:00:01-05:00")]
    rejected=select(late,deadline)
    assert rejected["status"]=="UNAVAILABLE" and rejected["reason"]=="no document before deadline"
    stale=select([dict(DocID="authored-stale",PublishDate="2026-10-24T09:00:00-05:00")],deadline)
    assert stale["status"]=="UNAVAILABLE" and stale["reason"]=="latest eligible document is stale"
    result=dict(status="PASS",cases=3,conditions=6,real_archive_selection=real,authored_late_only=rejected,authored_stale=stale,scope="Local deterministic exercises; no production user or operational decision")
    out.mkdir(parents=True,exist_ok=True)
    (out/"exercise.json").write_bytes((json.dumps(result,indent=2)+"\n").encode())
    print(json.dumps(result))


if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--out",type=Path,default=ROOT/"results")
    execute(p.parse_args().out)
