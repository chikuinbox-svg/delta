import httpx
import pytest
from delta_lab.api import PublicAPI
from delta_lab.storage import frame, quality, Store
from delta_lab.download import Downloader


def bars(start=0, n=4, step=60):
    return [dict(time=start+i*step,open=10.,high=12.,low=9.,close=11.,volume=5.) for i in range(n)]


def test_quality():
    rows=bars(); rows.pop(1); rows.append(rows[0])
    q=quality(frame(rows),60,0,240)
    assert q['duplicates']==1 and q['missing']==1 and q['invalid']==0
    rows[0]={**rows[0],'high':1}
    assert quality(frame(rows),60)['invalid']==1


def test_storage(tmp_path):
    s=Store(tmp_path); s.merge('BTCUSD','1m',frame(bars()))
    s.merge('BTCUSD','1m',frame(bars()))
    assert len(s.read('BTCUSD','1m'))==4
    assert s.snapshot('BTCUSD','1m')
    with pytest.raises(ValueError): s.read('../escape','1m')


def test_public_api_pagination_and_candles():
    seen=[]
    def handler(req):
        seen.append(req)
        if req.url.path.endswith('products'):
            after=req.url.params.get('after')
            return httpx.Response(200,json={'success':True,'result':[{'symbol': 'ETHUSD' if after else 'BTCUSD','contract_type':'perpetual_futures'}], 'meta':{} if after else {'after':'next'}})
        return httpx.Response(200,json={'success':True,'result':bars()})
    api=PublicAPI(transport=httpx.MockTransport(handler),delay=0)
    assert len(api.products())==2
    assert len(api.candles('BTCUSD','1m',0,240))==4
    with pytest.raises(ValueError): api.get('/v2/orders')
    api.close()


def test_resume_and_incremental(tmp_path):
    class API:
        calls=0
        fail=True
        def candles(self,s,r,start,end):
            self.calls+=1
            if start>=30000 and self.fail: raise ConnectionError('synthetic disconnect')
            return bars(start,(end-start)//60)
    api=API(); store=Store(tmp_path); d=Downloader(api,store)
    with pytest.raises(ConnectionError): d.download('BTCUSD','1m',0,36000)
    assert len(store.read('BTCUSD','1m'))==500
    api.fail=False; d.download('BTCUSD','1m',0,36000)
    assert len(store.read('BTCUSD','1m'))==600 and api.calls==3
    d.download('BTCUSD','1m',36000,36120)
    assert len(store.read('BTCUSD','1m'))==602


def test_incomplete_window_not_marked_complete(tmp_path):
    class API:
        def candles(self,*a): return []
    with pytest.raises(ValueError,match='Incomplete'):
        Downloader(API(),Store(tmp_path)).download('BTCUSD','1m',0,60)


def test_retry():
    calls=[]
    def handler(req):
        calls.append(req)
        return httpx.Response(429,headers={'Retry-After':'0'}) if len(calls)==1 else httpx.Response(200,json={'success':True,'result':[]})
    a=PublicAPI(transport=httpx.MockTransport(handler),delay=0)
    assert a.products()==[] and len(calls)==2
    a.close()


def test_checkpoint_does_not_mask_deleted_data(tmp_path):
    class API:
        calls=0
        def candles(self,s,r,a,b):
            self.calls+=1
            return bars(a,(b-a)//60)
    api=API(); store=Store(tmp_path); d=Downloader(api,store)
    d.download('BTCUSD','1m',0,240)
    (store.directory('BTCUSD','1m')/'candles.parquet').unlink()
    d.download('BTCUSD','1m',0,240)
    assert api.calls==2 and len(store.read('BTCUSD','1m'))==4
