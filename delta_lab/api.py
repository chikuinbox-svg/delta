"""Read-only public API. No arbitrary URLs, credentials or execution endpoints."""
from __future__ import annotations
import time
from datetime import datetime, timezone
import httpx

BASE = 'https://api.india.delta.exchange'
RESOLUTIONS = {'1m': 60, '3m': 180}

class PublicAPI:
    def __init__(self, transport=None, retries=4, delay=0.25):
        self.client = httpx.Client(base_url=BASE, timeout=30, transport=transport,
                                   headers={'User-Agent': 'DeltaResearchLab/0.1'})
        self.retries, self.delay = retries, delay

    def close(self):
        self.client.close()

    def get(self, path, params=None):
        if path not in {'/v2/products', '/v2/history/candles'}:
            raise ValueError('Only approved public market-data routes are allowed')
        for attempt in range(self.retries + 1):
            try:
                time.sleep(self.delay)
                response = self.client.get(path, params=params)
                if response.status_code == 429 or response.status_code >= 500:
                    if attempt == self.retries:
                        response.raise_for_status()
                    wait = response.headers.get('Retry-After', '')
                    time.sleep(min(float(wait) if wait.isdigit() else 2**attempt, 60))
                    continue
                response.raise_for_status()
                body = response.json()
                if body.get('success') is not True:
                    raise ValueError(f'Exchange rejected public request: {body.get("error")}')
                return body
            except httpx.TransportError:
                if attempt == self.retries:
                    raise
                time.sleep(min(2**attempt, 30))
        raise RuntimeError('Retry budget exhausted')

    def products(self):
        rows, after, seen = [], None, set()
        for _ in range(1000):
            params = {'page_size': 100}
            if after:
                params['after'] = after
            body = self.get('/v2/products', params)
            if not isinstance(body.get('result'), list):
                raise ValueError('Unexpected products schema')
            rows.extend(body['result'])
            after = body.get('meta', {}).get('after')
            if not after:
                break
            if after in seen:
                raise ValueError('Repeated product cursor')
            seen.add(after)
        else:
            raise ValueError('Product pagination exceeded safety limit')
        return [r for r in rows if r.get('contract_type') == 'perpetual_futures']

    def candles(self, symbol, resolution, start, end):
        if resolution not in RESOLUTIONS:
            raise ValueError('Select 1m or 3m')
        if start >= end:
            return []
        body = self.get('/v2/history/candles', {'symbol': symbol,
                        'resolution': resolution, 'start': int(start), 'end': int(end)})
        if not isinstance(body.get('result'), list):
            raise ValueError('Unexpected candle schema')
        return body['result']


def utc_now():
    return datetime.now(timezone.utc).isoformat()
