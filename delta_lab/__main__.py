"""Offline reproducibility audit of a saved simulation."""
import argparse
import hashlib
import json
from pathlib import Path
import polars as pl
from .config import RunConfig
from .engine import Engine
from .reporting import load_run
from .research import metrics
from .storage import ROOT


def verify_run(path):
    path=Path(path).resolve()
    if not path.is_relative_to(ROOT):
        raise ValueError('Reports must be inside this project directory')
    saved=load_run(path)
    data={}
    for sym,item in saved['manifest']['snapshots'].items():
        snapshot=(path.parent/item['file']).resolve()
        if not snapshot.is_relative_to(path.parent): raise ValueError('Invalid snapshot path')
        if hashlib.sha256(snapshot.read_bytes()).hexdigest()!=item['sha256']:
            raise ValueError(f'{sym}: input hash mismatch')
        data[sym]=pl.read_parquet(snapshot).to_dicts()
    current=Engine(RunConfig.model_validate(saved['config'])).run(data)
    for key in ('trades','equity','events'):
        if current[key]!=saved[key]: raise ValueError(f'Reproduction differs: {key}; check recorded source and dependency versions')
    return metrics(current)


def main():
    parser=argparse.ArgumentParser(description='Audit a saved Delta paper simulation without network access')
    parser.add_argument('command',choices=['verify-run'])
    parser.add_argument('result_json',type=Path)
    args=parser.parse_args()
    print(json.dumps(verify_run(args.result_json),indent=2))

if __name__=='__main__': main()
