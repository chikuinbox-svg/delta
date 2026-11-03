from __future__ import annotations
import time
from .api import RESOLUTIONS, utc_now
from .storage import frame, quality, atomic_json

class Downloader:
    """Single writer per project. Commit data before a checkpoint; retries are idempotent."""
    def __init__(self, api, store):
        self.api, self.store = api, store

    def catalogue(self):
        rows = self.api.products()
        # Append observations, never infer delistings from absence in one response.
        path = self.store.root / 'catalogue.jsonl'
        import json
        with path.open('a', encoding='utf-8') as f:
            f.write(json.dumps({'observed_at': utc_now(), 'products': rows})+'\n')
        return rows

    def download(self, symbol, resolution, start, end, progress=lambda _: None):
        import json
        step = RESOLUTIONS[resolution]
        if start % step or end % step or start >= end:
            raise ValueError('Use aligned UTC boundaries with start < end')
        if end > int(time.time()) // step * step:
            raise ValueError('End must exclude the unfinished candle')
        directory = self.store.directory(symbol,resolution)
        checkpoint = directory / f'checkpoint-{start}-{end}.json'
        cursor = start
        if checkpoint.exists():
            cursor = json.loads(checkpoint.read_text())['next']
        # A checkpoint alone is insufficient if retained data were removed or damaged.
        if cursor>start:
            retained=self.store.read(symbol,resolution,start,cursor)
            audit=quality(retained,step,start,cursor)
            if any(audit[k] for k in ('missing','duplicates','invalid','misaligned')):
                cursor=start
        begun, requests = time.monotonic(), 0
        while cursor < end:
            # Conservative 500-bar windows; server end inclusivity is neutralized by filtering.
            stop = min(end, cursor + 500*step)
            rows = self.api.candles(symbol,resolution,cursor,stop)
            raw = frame(rows)
            selected = raw.filter((raw['time'] >= cursor) & (raw['time'] < stop))
            report = quality(selected,step,cursor,stop)
            if report['invalid'] or report['misaligned']:
                atomic_json(directory/'last-rejected-quality.json',report)
                raise ValueError('Invalid candles rejected; inspect last-rejected-quality.json')
            self.store.merge(symbol,resolution,selected)
            # Missing windows remain retryable; never claim empty API output as full coverage.
            if report['missing']:
                atomic_json(checkpoint, {'next': cursor, 'end': end, 'quality': report, 'status': 'incomplete'})
                progress({'symbol':symbol,'next':cursor,'end':end,'quality':report,'eta_seconds':None})
                raise ValueError('Incomplete history window. Data saved; retry resumes this window. Coverage may predate listing or exceed API retention.')
            cursor = stop
            requests += 1
            atomic_json(checkpoint, {'next':cursor,'end':end,'quality':report,'status':'complete' if cursor==end else 'running'})
            elapsed = time.monotonic()-begun
            progress({'symbol':symbol,'next':cursor,'end':end,'quality':report,
                      'eta_seconds':elapsed/requests * ((end-cursor)/(500*step))})
        result = self.store.read(symbol,resolution,start,end)
        atomic_json(directory/'quality.json',quality(result,step,start,end))
        return result
