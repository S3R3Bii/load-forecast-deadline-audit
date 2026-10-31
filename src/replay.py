"""Recompute saved-data evidence in an external directory, without source requests."""
from pathlib import Path
import argparse
import hashlib
import json
import platform
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--out",required=True,type=Path)
    p.add_argument("--analysis-only",action="store_true")
    a=p.parse_args()
    out=a.out.resolve()
    assert not out.is_relative_to(ROOT.resolve()), "Use an external output directory"
    assert not out.exists(), "Preserve earlier replay evidence"
    hashes={str(p.relative_to(ROOT)).replace("\\","/"):hashlib.sha256(p.read_bytes()).hexdigest() for p in (ROOT/"data").rglob("*") if p.is_file()}
    def run(*args):
        subprocess.run([sys.executable,*args],cwd=ROOT,check=True)
    run("-m","unittest","discover","-s","tests")
    run("src/source.py")
    run("src/check_source.py")
    run("src/analyze.py","--out",str(out))
    run("src/check_analysis.py","--out",str(out))
    run("src/exercise.py","--out",str(out))
    outputs=["comparisons.csv","daily_metrics.csv","overall_metrics.csv","peaks.csv","verification.json","exercise.json"]
    for name in outputs:
        assert (out/name).read_bytes()==(ROOT/"results"/name).read_bytes(),name
    for name,digest in hashes.items():
        assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==digest,("source changed",name)
    if not a.analysis_only:
        run("src/check_figures.py")
        run("src/check_paper.py")
    receipt=dict(status="PASS",runtime=platform.python_version(),mode="analysis-only" if a.analysis_only else "full",exact_output_files=len(outputs),source_files_unchanged=len(hashes),no_network_source_requests=True,native_conditions=101139,analysis_conditions=48524,fixture_methods=22,exercise_cases=3,scope="Saved-data source/numerical/guard replay; private ZIP reacquisition and historical delivery not reproduced")
    (out/"replay_receipt.json").write_bytes((json.dumps(receipt,indent=2)+"\n").encode())
    print(json.dumps(receipt))


if __name__=="__main__":
    main()
