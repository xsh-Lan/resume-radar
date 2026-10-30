#!/usr/bin/env python3
"""Run behavioral invariants; optional validation of an actual analyzed run."""
import argparse
import json
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from workflow import validate_run

def main():
    p=argparse.ArgumentParser(description=__doc__); p.add_argument('--run-dir'); args=p.parse_args()
    suite=unittest.defaultTestLoader.discover(str(Path(__file__).parent),pattern='test_*.py')
    result=unittest.TextTestRunner(verbosity=2).run(suite)
    if args.run_dir:
        report=validate_run(args.run_dir); print(json.dumps(report,ensure_ascii=False,indent=2))
        if not report['ok']:return 1
    return 0 if result.wasSuccessful() else 1

if __name__=='__main__':raise SystemExit(main())
