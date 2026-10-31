"""Describe every prespecified cutoff; no fitting, search or selection by errors."""

from pathlib import Path
from datetime import datetime
from decimal import Decimal, localcontext
from collections import defaultdict
import argparse
import csv
import json

ROOT = Path(__file__).resolve().parents[1]
D = Decimal


def dump_csv(path, rows):
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]), lineterminator="\n")
        w.writeheader()
        w.writerows(rows)


def metrics(rows):
    errors = [D(r["error_mw"]) for r in rows]
    n = len(rows)
    absolute = sum(map(abs, errors), D(0))
    square = sum((x * x for x in errors), D(0))
    signed = sum(errors, D(0))
    load = sum((D(r["actual_mw"]) for r in rows if D(r["actual_mw"]) > 0), D(0))
    return dict(
        n=n,
        sum_absolute=absolute,
        sum_squared=square,
        sum_error=signed,
        sum_positive_actual=load,
        mae_mw=absolute / n,
        mse_mw2=square / n,
        rmse_mw=(square / n).sqrt(),
        mean_error_mw=signed / n,
        wape=absolute / load if load else "UNAVAILABLE",
        max_absolute_mw=max(map(abs, errors)),
        max_under_mw=max(D(0), max(-x for x in errors)),
        published_after_start=sum(r["published_after_start"] for r in rows),
        published_after_end=sum(r["published_after_end"] for r in rows),
        violates_day_ahead=sum(r["violates_day_ahead"] for r in rows),
    )


def peak_summary(rows):
    fp = max(r["forecast_mw"] for r in rows)
    ap = max(r["actual_mw"] for r in rows)
    fh = sorted(r["hour_ending"] for r in rows if r["forecast_mw"] == fp)
    ah = sorted(r["hour_ending"] for r in rows if r["actual_mw"] == ap)
    return dict(
        forecast_peak_mw=fp,
        actual_peak_mw=ap,
        peak_error_mw=fp - ap,
        forecast_peak_hours="|".join(map(str, fh)),
        actual_peak_hours="|".join(map(str, ah)),
        includes_actual_peak=int(bool(set(fh) & set(ah))),
    )


def execute(out):
    plan = json.loads((ROOT / "data/source_plan.json").read_bytes())
    source = list(
        csv.DictReader((ROOT / "data/qualified.csv").open(encoding="utf-8", newline=""))
    )
    refs = {}
    for r in source:
        if r["kind"] == "actual":
            key = (r["day"], r["hour_ending"], r["zone"])
            assert key not in refs
            refs[key] = r
    pairs = []
    for r in source:
        if r["kind"] != "forecast":
            continue
        actual = refs[(r["day"], r["hour_ending"], r["zone"])]
        f, a = D(r["load_mw"]), D(actual["load_mw"])
        stamp = datetime.fromisoformat(r["published"])
        start, end = map(
            datetime.fromisoformat, [r["interval_start"], r["interval_end"]]
        )
        prior = datetime.fromisoformat(r["day"] + "T12:00:00-05:00")
        from datetime import timedelta

        prior -= timedelta(days=1)
        pairs.append(
            dict(
                day=r["day"],
                hour_ending=int(r["hour_ending"]),
                zone=r["zone"],
                policy=r["policy"],
                forecast_mw=f,
                actual_mw=a,
                error_mw=f - a,
                absolute_mw=abs(f - a),
                squared_mw2=(f - a) ** 2,
                forecast_doc=r["doc_id"],
                actual_doc=actual["doc_id"],
                published=r["published"],
                actual_published=actual["published"],
                interval_start=r["interval_start"],
                interval_end=r["interval_end"],
                published_after_start=int(stamp > start),
                published_after_end=int(stamp > end),
                violates_day_ahead=int(stamp > prior),
            )
        )
    assert len(pairs) == plan["expected_comparisons"]
    daily = defaultdict(list)
    overall = defaultdict(list)
    for r in pairs:
        daily[(r["day"], r["zone"], r["policy"])].append(r)
        overall[(r["zone"], r["policy"])].append(r)
    daily_rows = [
        dict(day=k[0], zone=k[1], policy=k[2], **metrics(v))
        for k, v in sorted(daily.items())
    ]
    overall_rows = [
        dict(zone=k[0], policy=k[1], **metrics(v)) for k, v in sorted(overall.items())
    ]
    peaks = []
    for (day, zone, policy), v in sorted(daily.items()):
        peaks.append(dict(day=day, zone=zone, policy=policy, **peak_summary(v)))
    out.mkdir(parents=True, exist_ok=True)
    dump_csv(out / "comparisons.csv", pairs)
    dump_csv(out / "daily_metrics.csv", daily_rows)
    dump_csv(out / "overall_metrics.csv", overall_rows)
    dump_csv(out / "peaks.csv", peaks)
    assert (
        len(daily_rows) == plan["expected_daily_metrics"]
        and len(overall_rows) == plan["expected_overall_metrics"]
        and len(peaks) == plan["expected_peaks"]
    )
    print(
        json.dumps(
            dict(
                status="ALL_FIXED_CASES_DESCRIBED",
                comparisons=len(pairs),
                daily_metrics=len(daily_rows),
                overall_metrics=len(overall_rows),
                peaks=len(peaks),
            )
        )
    )


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--out", type=Path, default=ROOT / "results")
    a = p.parse_args()
    with localcontext() as c:
        c.prec = 60
        execute(a.out)


if __name__ == "__main__":
    main()
