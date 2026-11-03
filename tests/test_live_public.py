"""Explicit opt-in real-data integration; never uses trading authentication."""
import os,time
import pytest
from delta_lab.api import PublicAPI
from delta_lab.download import Downloader
from delta_lab.storage import Store,ROOT

@pytest.mark.skipif(os.environ.get('DELTA_RUN_PUBLIC_INTEGRATION')!='1',reason='Public API access and current contract verification required; opt in explicitly')
def test_real_historical_sample():
    api=PublicAPI()
    try:
        products=api.products()
        assert products and any(p['symbol']=='BTCUSD' for p in products)
        end=int(time.time())//180*180-180
        df=Downloader(api,Store(ROOT/'data'/'integration-sample')).download('BTCUSD','3m',end-180*10,end)
        assert len(df)==10 and df['close'].min()>0
    finally: api.close()
