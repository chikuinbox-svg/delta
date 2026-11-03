from __future__ import annotations
import hashlib
import json
import os
import re
from pathlib import Path
import duckdb
import polars as pl

ROOT = Path(__file__).resolve().parents[1]
COLUMNS = ['time', 'open', 'high', 'low', 'close', 'volume']
SCHEMA = {'time': pl.Int64, **{c: pl.Float64 for c in COLUMNS[1:]}}


def atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + '.tmp')
    temp.write_text(json.dumps(value, indent=2, default=str), encoding='utf-8')
    os.replace(temp, path)


def frame(rows):
    if not rows:
        return pl.DataFrame(schema=SCHEMA)
    return pl.DataFrame(rows).select([pl.col(c).cast(dtype, strict=True) for c, dtype in SCHEMA.items()])


def quality(df, seconds, start=None, end=None):
    """All intervals are [start,end); timestamps denote candle opens."""
    if df.is_empty():
        return {'rows': 0, 'duplicates': 0, 'missing': max(0, (end-start)//seconds) if start is not None and end is not None else 0,
                'misaligned': 0, 'invalid': 0, 'incomplete': 0, 'missing_preview': []}
    times = sorted(set(df['time'].to_list()))
    start = times[0] if start is None else start
    end = times[-1] + seconds if end is None else end
    valid_times = set(times)
    missing = [t for t in range(start, end, seconds) if t not in valid_times]
    invalid = 0
    import math, time
    for r in df.iter_rows(named=True):
        nums = [r[c] for c in COLUMNS[1:]]
        if any(v is None or not math.isfinite(v) for v in nums) or min(nums[:4]) <= 0 or r['volume'] < 0 or r['high'] < max(r['open'],r['close'],r['low']) or r['low'] > min(r['open'],r['close']):
            invalid += 1
    return {'rows': len(df), 'duplicates': len(df)-len(times), 'missing': len(missing),
            'misaligned': sum(t % seconds != 0 for t in df['time']), 'invalid': invalid,
            'incomplete': sum(t+seconds > time.time() for t in times), 'missing_preview': missing[:100]}


class Store:
    def __init__(self, root=ROOT / 'data'):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def directory(self, symbol, resolution):
        if not re.fullmatch(r'[A-Za-z0-9_-]{1,80}', symbol) or resolution not in {'1m','3m'}:
            raise ValueError('Invalid symbol or resolution')
        path = self.root / symbol / resolution
        path.mkdir(parents=True, exist_ok=True)
        return path

    def read(self, symbol, resolution, start=None, end=None):
        path = self.directory(symbol, resolution) / 'candles.parquet'
        if not path.exists():
            return frame([])
        with duckdb.connect() as con:
            df = con.execute('SELECT * FROM read_parquet(?) ORDER BY time', [str(path)]).pl()
        if start is not None:
            df = df.filter(pl.col('time') >= start)
        if end is not None:
            df = df.filter(pl.col('time') < end)
        return df

    def merge(self, symbol, resolution, df):
        old = self.read(symbol, resolution)
        combined = pl.concat([old,df]).unique(subset=['time'],keep='last').sort('time')
        path = self.directory(symbol, resolution) / 'candles.parquet'
        tmp = path.with_suffix('.parquet.tmp')
        combined.write_parquet(tmp, compression='zstd')
        os.replace(tmp, path)
        return combined

    def snapshot(self, symbol, resolution):
        path = self.directory(symbol,resolution) / 'candles.parquet'
        return hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None
