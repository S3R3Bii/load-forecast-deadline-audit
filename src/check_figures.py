"""Reconstruct every actual SVG bar vertex and label from exported metrics."""

from pathlib import Path
from decimal import Decimal
import csv
import hashlib
import json
import re
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
NS = {"s": "http://www.w3.org/2000/svg"}
checks = 0


def require(ok, detail):
    global checks
    checks += 1
    assert ok, detail


def vertices(group):
    path = group.find(".//s:path", NS)
    return [
        float(x)
        for x in re.findall(r"[-+]?(?:\d*\.)?\d+(?:[eE][-+]?\d+)?", path.attrib["d"])
    ]


ledger = json.loads((ROOT / "figures/ledger.json").read_bytes())
by_id = {x["id"]: x for x in ledger["bars"]}
count = 0
for filename, prefix, n, orientation, xrange, yrange in [
    ("system_cutoffs", "overall", 3, "v", (-0.6, 2.6), (0, 1200)),
    ("daily_system_errors", "daily", 15, "h", (0, 1800), (-0.6, 4.6)),
    ("all_series_wape", "zone", 27, "h", (0, 9.5), (-0.6, 8.6)),
]:
    svg = ET.parse(ROOT / "figures" / (filename + ".svg"))
    ids = {e.attrib["id"]: e for e in svg.iter() if "id" in e.attrib}
    axes = ids["audit_axes"]
    patch = next(
        e
        for e in axes
        if e.tag.endswith("g") and e.attrib.get("id", "").startswith("patch_")
    )
    border = vertices(patch)
    xmin, xmax = min(border[::2]), max(border[::2])
    ymin, ymax = min(border[1::2]), max(border[1::2])
    tx = lambda v: xmin + (v - xrange[0]) / (xrange[1] - xrange[0]) * (xmax - xmin)
    ty = lambda v: (
        ymax - (v - yrange[0]) / (yrange[1] - yrange[0]) * (ymax - ymin)
        if orientation == "v"
        else ymin + (v - yrange[0]) / (yrange[1] - yrange[0]) * (ymax - ymin)
    )
    entries = [r for r in ledger["bars"] if r["id"].startswith(prefix + "_")]
    require(len(entries) == n, "full figure support")
    for item in entries:
        source = item["source"]
        rows = list(
            csv.DictReader(
                (ROOT / "results" / source["file"]).open(encoding="utf-8", newline="")
            )
        )
        row = [
            r
            for r in rows
            if all(
                r.get(k) == source[k] for k in ["zone", "policy", "day"] if k in source
            )
        ]
        require(len(row) == 1, "unique bound metric")
        value = float(Decimal(row[0][source["field"]]) * source.get("scale", 1))
        require(abs(value - item["value"]) < 1e-10, "ledger metric")
        parts = item["id"].split("_")
        if orientation == "v":
            center = int(parts[1])
            expected = [
                tx(center - 0.29),
                ty(0),
                tx(center + 0.29),
                ty(0),
                tx(center + 0.29),
                ty(value),
                tx(center - 0.29),
                ty(value),
            ]
            lx, ly = tx(center), ty(value + 30)
        else:
            center = int(parts[1]) + (int(parts[2]) - 1) * 0.24
            expected = [
                tx(0),
                ty(center - 0.105),
                tx(value),
                ty(center - 0.105),
                tx(value),
                ty(center + 0.105),
                tx(0),
                ty(center + 0.105),
            ]
            lx, ly = tx(value + (22 if source["field"] == "mae_mw" else 0.10)), ty(
                center
            )
        observed = vertices(ids["bar_" + item["id"]])
        require(len(observed) == 8, "rectangle vertices")
        for left, right in zip(observed, expected):
            require(abs(left - right) < 1e-5, "actual SVG vertex")
        text = ids["label_" + item["id"]].find(".//s:text", NS)
        require("".join(text.itertext()) == f"{value:.1f}", "actual numeric label")
        require(
            abs(float(text.attrib["x"]) - lx) < 1e-5
            and abs(float(text.attrib["y"]) - ly) < 5,
            "actual label placement",
        )
        count += 1
for name, digest in ledger["assets_sha256"].items():
    require(
        hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == digest,
        "current figure bytes",
    )
result = dict(
    status="PASS",
    conditions=checks,
    source_bound_bars=count,
    svg_vertex_coordinates=count * 8,
    numeric_labels=count,
    asset_hashes=len(ledger["assets_sha256"]),
    scope="All source bindings, actual SVG rectangle geometry and numeric label placement; PNG/PDF appearance reviewed separately",
)
(ROOT / "figures/verification.json").write_bytes(
    (json.dumps(result, indent=2) + "\n").encode()
)
print(json.dumps(result))
