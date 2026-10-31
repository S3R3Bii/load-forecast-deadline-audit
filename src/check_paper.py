"""Verify actual used TeX bindings, PDF text, source qualifiers and scoped bytes."""

from pathlib import Path
from decimal import Decimal
import csv
import hashlib
import json
import re
from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[1]
checks = 0


def require(ok, detail):
    global checks
    checks += 1
    assert ok, detail


tex = (ROOT / "paper/main.tex").read_text(encoding="utf-8")
pdf = PdfReader(ROOT / "paper/manuscript.pdf")
text = "\n".join(p.extract_text() or "" for p in pdf.pages).replace("\u2212", "-")
compact = re.sub(r"\s+", " ", text)
require(len(pdf.pages) == 5, "five rendered pages")
bindings = json.loads((ROOT / "paper/bindings.json").read_bytes())
require(
    len(bindings) == 43 and len({r["name"] for r in bindings}) == 43,
    "complete unique bindings",
)
for b in bindings:
    if b["kind"] == "csv":
        rows = list(
            csv.DictReader((ROOT / b["file"]).open(encoding="utf-8", newline=""))
        )
        matching = [r for r in rows if all(r[k] == v for k, v in b["query"].items())]
        require(len(matching) == 1, "source query support")
        expected = f"{Decimal(matching[0][b['field']])*b['scale']:.{b['digits']}f}"
    else:
        expected = str(json.loads((ROOT / b["file"]).read_bytes())[b["field"]])
    require(expected == b["display"], "display matches source")
    definition = "\\newcommand{\\" + b["name"] + "}{" + expected + "}"
    require(definition in tex, "actual macro value")
    require(
        len(re.findall(r"\\" + re.escape(b["name"]) + r"\b", tex)) >= 2,
        "macro used beyond definition",
    )
    require(expected in text, "actual PDF numeric display")
for phrase in [
    "Not peer reviewed",
    "five adjacent days",
    "archive metadata",
    "not a reserve-policy improvement",
    "not a claim about ERCOT",
    "all 120 hours",
    "after 115",
    "not nine independent",
    "learned residual corrections",
    "remains unexecuted",
    "No reserve saving",
    "no production user",
    "immutable original content",
]:
    require(phrase.casefold() in compact.casefold(), ("qualification", phrase))
source = list(
    csv.DictReader((ROOT / "data/qualified.csv").open(encoding="utf-8", newline=""))
)
require(
    all(Decimal(r["load_mw"]) > 0 for r in source if r["kind"] == "actual"),
    "paper positive actuals statement",
)
freeze = json.loads((ROOT / "ANALYSIS_FREEZE.json").read_bytes())
require(
    len(freeze["sha256"]) == 53 and freeze["first_error_scoring_run"] is False,
    "freeze statement",
)
overall = list(
    csv.DictReader(
        (ROOT / "results/overall_metrics.csv").open(encoding="utf-8", newline="")
    )
)
end = next(
    r for r in overall if r["zone"] == "SystemTotal" and r["policy"] == "end_of_day"
)
require(
    end["published_after_end"] == "115" and end["violates_day_ahead"] == "120",
    "late interval claims",
)
peaks = list(
    csv.DictReader((ROOT / "results/peaks.csv").open(encoding="utf-8", newline=""))
)
require(
    sum(
        int(r["includes_actual_peak"])
        for r in peaks
        if r["zone"] == "SystemTotal" and r["policy"] == "day_ahead"
    )
    == 3,
    "three of five peak-hour sets",
)
for version in ["310", "312"]:
    receipt = json.loads(
        (ROOT / ("results/reproduction_cpython" + version + ".json")).read_bytes()
    )
    require(
        receipt["status"] == "PASS"
        and receipt["exact_output_files"] == 6
        and receipt["source_files_unchanged"] == 40,
        "two runtime replay statement",
    )
scope = json.loads((ROOT / "paper/PUBLICATION_SCOPE.json").read_bytes())
require(
    scope["scope"] == "independent-program-study"
    and scope["formal_submission_target"] is False
    and len(scope["public_files"]) == 5,
    "scoped independent manuscript",
)
for name, digest in scope["public_files"].items():
    require(
        hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == digest,
        ("scoped bytes", name),
    )
for name in ["system_cutoffs", "daily_system_errors", "all_series_wape"]:
    require(
        (ROOT / ("paper/images/" + name + ".pdf")).read_bytes()
        == (ROOT / ("figures/" + name + ".pdf")).read_bytes(),
        "current figure copy",
    )
require(
    hashlib.sha256((ROOT / "paper/manuscript.pdf").read_bytes()).hexdigest()
    == json.loads((ROOT / "paper/visual_review.json").read_bytes())[
        "manuscript_sha256"
    ],
    "reviewed PDF hash",
)
result = dict(
    status="PASS",
    conditions=checks,
    used_numeric_bindings=len(bindings),
    pages=len(pdf.pages),
    scope_files=5,
    scope="Used TeX macros, PDF numeric text, source-bound qualifications, finite replay facts, scoped bytes and visual-review hash; visual inspection is separately recorded",
)
(ROOT / "paper/verification.json").write_bytes(
    (json.dumps(result, indent=2) + "\n").encode()
)
print(json.dumps(result))
