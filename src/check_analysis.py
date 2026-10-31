"""Independent SQLite source joins and exact rational error/peak reconstruction."""
from pathlib import Path
from datetime import datetime
from fractions import Fraction as Q
from decimal import Decimal, localcontext
import argparse
import csv
import hashlib
import json
import sqlite3

ROOT=Path(__file__).resolve().parents[1]
CHECKS=0
MAX_ERROR=Decimal(0)


def require(ok,detail):
    global CHECKS
    CHECKS+=1
    assert ok,detail


def numeric(text,expected,exact=False):
    global MAX_ERROR
    if isinstance(expected,str):
        require(text==expected,"unavailable value")
    elif exact:
        require(Q(text)==expected,"exact arithmetic")
    else:
        target=Decimal(expected.numerator)/Decimal(expected.denominator) if isinstance(expected,Q) else expected
        delta=abs(Decimal(text)-target)
        MAX_ERROR=max(MAX_ERROR,delta)
        require(delta<=Decimal("1e-45"),"derived arithmetic")


def read(out,name):
    return list(csv.DictReader((out/name).open(encoding="utf-8",newline="")))


def check(out):
    freeze=json.loads((ROOT/"ANALYSIS_FREEZE.json").read_bytes())
    for name,digest in freeze["sha256"].items():
        require(hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==digest,("frozen dependency",name))
    source=read(ROOT/"data","qualified.csv")
    db=sqlite3.connect(":memory:")
    db.execute("create table source(kind,day,policy,hour integer,zone,value,doc,pub,start,end)")
    for r in source:
        db.execute("insert into source values(?,?,?,?,?,?,?,?,?,?)",(r["kind"],r["day"],r["policy"],int(r["hour_ending"]),r["zone"],r["load_mw"],r["doc_id"],r["published"],r["interval_start"],r["interval_end"]))
    tuples=db.execute("select f.day,f.hour,f.zone,f.policy,f.value,a.value,f.doc,a.doc,f.pub,a.pub,f.start,f.end from source f join source a on f.day=a.day and f.hour=a.hour and f.zone=a.zone and a.kind='actual' where f.kind='forecast' order by f.day,f.policy,f.hour,f.zone").fetchall()
    comparisons=read(out,"comparisons.csv")
    keyed={(r["day"],int(r["hour_ending"]),r["zone"],r["policy"]):r for r in comparisons}
    require(len(tuples)==len(keyed)==len(comparisons)==3240,"complete comparison support")
    expected={}
    for day,hour,zone,policy,f,a,fd,ad,pub,apub,start,end in tuples:
        key=(day,hour,zone,policy)
        r=keyed[key]
        fq,aq=Q(f),Q(a)
        e=fq-aq
        after_start=int(datetime.fromisoformat(pub)>datetime.fromisoformat(start))
        after_end=int(datetime.fromisoformat(pub)>datetime.fromisoformat(end))
        from datetime import timedelta
        deadline=datetime.fromisoformat(day+"T12:00:00-05:00")-timedelta(days=1)
        late=int(datetime.fromisoformat(pub)>deadline)
        for field,val in dict(forecast_doc=fd,actual_doc=ad,published=pub,actual_published=apub,interval_start=start,interval_end=end).items():
            require(r[field]==val,("lineage",field))
        for field,val in dict(forecast_mw=fq,actual_mw=aq,error_mw=e,absolute_mw=abs(e),squared_mw2=e*e,published_after_start=Q(after_start),published_after_end=Q(after_end),violates_day_ahead=Q(late)).items():
            numeric(r[field],val,exact=True)
        expected[key]=(fq,aq,e,after_start,after_end,late)
    for filename,daily,size in [("overall_metrics.csv",False,27),("daily_metrics.csv",True,135)]:
        exported=read(out,filename)
        require(len(exported)==size,"metric support")
        keys=[(r.get("day","ALL"),r["zone"],r["policy"]) for r in exported]
        require(len(set(keys))==size,"metric uniqueness")
        for r,(day,zone,policy) in zip(exported,keys):
            subset=[v for k,v in expected.items() if k[2]==zone and k[3]==policy and (not daily or k[0]==day)]
            n=len(subset)
            absolute=sum((abs(v[2]) for v in subset),Q(0))
            square=sum((v[2]*v[2] for v in subset),Q(0))
            signed=sum((v[2] for v in subset),Q(0))
            load=sum((v[1] for v in subset if v[1]>0),Q(0))
            exact=dict(n=Q(n),sum_absolute=absolute,sum_squared=square,sum_error=signed,sum_positive_actual=load,max_absolute_mw=max(abs(v[2]) for v in subset),max_under_mw=max(Q(0),max(-v[2] for v in subset)),published_after_start=Q(sum(v[3] for v in subset)),published_after_end=Q(sum(v[4] for v in subset)),violates_day_ahead=Q(sum(v[5] for v in subset)))
            for field,val in exact.items():
                numeric(r[field],val,exact=True)
            derived=dict(mae_mw=absolute/n,mse_mw2=square/n,rmse_mw=(Decimal(square.numerator)/Decimal(square.denominator)/n).sqrt(),mean_error_mw=signed/n,wape=absolute/load if load else "UNAVAILABLE")
            for field,val in derived.items():
                numeric(r[field],val)
    peaks=read(out,"peaks.csv")
    require(len(peaks)==len({(r["day"],r["zone"],r["policy"]) for r in peaks})==135,"peak support")
    for r in peaks:
        sub={k[1]:v for k,v in expected.items() if k[0]==r["day"] and k[2]==r["zone"] and k[3]==r["policy"]}
        fm=max(v[0] for v in sub.values())
        am=max(v[1] for v in sub.values())
        fh={h for h,v in sub.items() if v[0]==fm}
        ah={h for h,v in sub.items() if v[1]==am}
        for field,val in dict(forecast_peak_mw=fm,actual_peak_mw=am,peak_error_mw=fm-am,includes_actual_peak=Q(int(bool(fh&ah)))).items():
            numeric(r[field],val,exact=True)
        require(r["forecast_peak_hours"]=="|".join(map(str,sorted(fh))) and r["actual_peak_hours"]=="|".join(map(str,sorted(ah))),"all peak ties")
    result=dict(status="PASS",conditions=CHECKS,comparison_rows=3240,metric_rows=162,peak_rows=135,maximum_derived_error=str(MAX_ERROR),tolerance_absolute="1e-45",scope="Independent SQLite source joins, exact Fraction sums, 80-digit derived metrics, provenance, all timing flags and peak ties; not immutable historical delivery proof")
    (out/"verification.json").write_bytes((json.dumps(result,indent=2)+"\n").encode())
    print(json.dumps(result))


if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--out",type=Path,default=ROOT/"results")
    a=p.parse_args()
    with localcontext() as c:
        c.prec=80
        check(a.out)
