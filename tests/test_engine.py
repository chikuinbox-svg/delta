import copy
import pytest
from delta_lab.config import RunConfig,Strategy,Execution,Instrument
from delta_lab.engine import Engine
from delta_lab.indicators import rsi,crossing,relative_volume
from delta_lab.strategy import signals
from delta_lab.execution import tick


def config(**kwargs):
    c=RunConfig(strategy=Strategy(initial_stop_range=1,research_rules_confirmed=True,min_30m_inr=0),
       execution=Execution(acknowledge_estimates=True,slippage_bps=0,spread_bps=0,fee_bps=0),
       instruments=[Instrument(symbol='BTCUSD',tick_size=.1,contract_size=1,quote_to_inr=1,volume_unit='base',metadata_confirmed=True)])
    for k,v in kwargs.items(): setattr(c.strategy,k,v)
    return c


def rows(values):
    return [dict(time=i*180,open=o,high=h,low=l,close=cl,volume=10000.) for i,(o,h,l,cl) in enumerate(values)]


def signal(d=1,trigger=101):
    return {'BTCUSD':{0:dict(direction=d,trigger=trigger,range=2,rsi=75,relative_volume=2,signal_time=180)}}


def run(data,c=None,sig=None): return Engine(c or config()).run({'BTCUSD':data},signal_overrides=sig or signal())


def test_wilder_rsi_and_fresh_crossings():
    assert rsi([1]*25,18)[18]==50
    assert rsi(list(range(25)),18)[18]==100
    assert rsi(list(range(25,0,-1)),18)[18]==0
    assert crossing(73,74,73,27)==1 and crossing(74,75,73,27)==0
    assert crossing(27,26,73,27)==-1
    assert relative_volume([1]*20+[4],20)==4


def test_no_lookahead():
    data=rows([(100+i%7,102+i%7,99+i%7,101+i%7) for i in range(80)])
    c=config(relative_volume=.01)
    a=signals(data[:50],c.strategy,c.instruments[0]); b=signals(data,c.strategy,c.instruments[0])
    assert a=={t:s for t,s in b.items() if t<50*180}
    assert rsi([r['close'] for r in data[:50]])==rsi([r['close'] for r in data])[:50]


def test_long_stop_and_no_same_signal_bar_fill():
    result=run(rows([(100,110,90,100),(102,104,98,102)]))
    assert result['trades'][0]['entry_time']==180
    assert result['trades'][0]['reason']=='same_bar_stop'
    assert result['trades'][0]['net_pnl']<0


def test_short_stop():
    result=run(rows([(100,102,98,100),(98,102,96,98)]),sig=signal(-1,99))
    assert result['trades'][0]['net_pnl']<0
    assert result['trades'][0]['stop']>result['trades'][0]['entry']


def test_expiry():
    result=run(rows([(100,100,99,100),(100,100,99,100),(100,110,99,105)]),config(expiry_bars=1))
    assert not result['trades']
    assert any(e['event']=='pending_expired' for e in result['events'])


def test_ambiguity_scenarios():
    data=rows([(100,100,99,100),(100,104,98,103)])
    outputs=[]
    for mode in ('conservative','optimistic','exclude'):
        c=config(); c.execution.scenario=mode
        outputs.append(run(data,c))
    assert outputs[0]['trades'][0]['reason']=='same_bar_stop'
    assert outputs[1]['trades'][0]['net_pnl']>outputs[0]['trades'][0]['net_pnl']
    assert not outputs[2]['trades']


def test_fees_cash_and_funding_reconcile():
    c=config(); c.execution.fee_bps=5; c.execution.funding_bps_per_8h=1
    r=run(rows([(100,100,99,100),(102,104,102,103),(103,106,103,105)]),c)
    tr=r['trades'][0]
    assert tr['fees']>0 and tr['funding']>0
    assert tr['net_pnl']==pytest.approx(tr['gross_pnl']-tr['fees']-tr['funding'])
    assert r['equity'][-1]['cash']==pytest.approx(c.capital_inr+tr['net_pnl'])


def test_insufficient_margin():
    c=config(); c.capital_inr=10
    r=run(rows([(100,100,99,100),(102,104,102,103)]),c)
    assert not r['trades'] and any(e.get('reason')=='insufficient margin' for e in r['events'])


def test_trailing_effective_next_bar():
    c=config(trail_activation_range=1,trail_distance_range=1)
    r=run(rows([(100,100,99,100),(102,104,102,103),(103,108,102,107),(106,108,104,107)]),c)
    assert any(e['event']=='trailing_stop' for e in r['events'])
    assert r['trades'][0]['exit_time']==540


def test_daily_protection():
    c=config(daily_loss_inr=1)
    r=run(rows([(100,100,99,100),(102,104,98,103),(103,110,102,109)]),c)
    assert any(e['event']=='daily_halt' for e in r['events'])


def test_restart_reproducibility():
    data=rows([(100,100,99,100),(102,104,102,103),(103,108,102,107),(106,108,104,107)])
    c=config(); a=run(data,c); b=run(data,c)
    assert a==b
    c.execution.stress_restart_every=1
    restored=run(data,c)
    assert restored['trades']==a['trades'] and restored['equity']==a['equity']


def test_disconnect_attached_stop_survives():
    c=config(); c.execution.stress_disconnect_every=2
    r=run(rows([(100,100,99,100),(102,104,102,103),(102,104,98,100)]),c)
    assert r['trades'][0]['reason']=='protective_stop'
    assert any(e['event']=='simulated_disconnect' for e in r['events'])


def test_multisymbol_position_limit_and_ordering():
    c=config(max_positions=1)
    c.instruments.append(c.instruments[0].model_copy(update={'symbol':'ETHUSD'}))
    data=rows([(100,100,99,100),(102,104,102,103)])
    sig=signal(); sig['ETHUSD']=copy.deepcopy(sig['BTCUSD'])
    a=Engine(c).run({'ETHUSD':data,'BTCUSD':data},sig)
    b=Engine(c).run({'BTCUSD':data,'ETHUSD':data},sig)
    assert a==b and len(a['trades'])==1
    assert a['trades'][0]['symbol']=='BTCUSD'


def test_guardrails():
    with pytest.raises(ValueError,match='Confirm'): Engine(RunConfig())
    c=config(min_open_interest=1)
    with pytest.raises(ValueError,match='historical'): Engine(c)
    c=config(); c.execution.fee_role='maker'
    with pytest.raises(ValueError,match='taker'): Engine(c)


def test_gap_data_rejected():
    data=rows([(100,101,99,100)]*4); data.pop(1)
    with pytest.raises(ValueError,match='quality'): run(data)


def test_tick_rounding():
    assert tick(1.234,.01,True)==1.24 and tick(1.234,.01,False)==1.23


def test_entry_trigger_formula():
    # Construct a genuine late fresh crossing after 10+ completed candles.
    prices=[100,99,98,97,96,95,94,93,92,91,90,120]
    data=rows([(p,p+1,p-1,p) for p in prices]); data[-1]['volume']=30000
    c=config(rsi_length=2,volume_lookback=2,relative_volume=1.8)
    sig=signals(data,c.strategy,c.instruments[0])
    assert sig and sig[1980]['trigger']==122
    assert sig[1980]['signal_time']==2160


def test_partial_fill_and_liquidation():
    c=config(); c.execution.estimate_partial_fills=True; c.execution.participation=.001
    r=run(rows([(100,100,99,100),(102,104,102,103)]),c)
    assert r['trades'][0]['quantity']==10
    c=config(initial_stop_range=100,monetary_stop_inr=100000)
    c.execution.maintenance_margin_pct=1
    r=run(rows([(100,100,99,100),(102,104,102,103),(102,103,50,60)]),c)
    assert r['trades'][0]['reason']=='estimated_liquidation'


def test_exit_frees_capacity_only_for_next_bar():
    c=config(max_positions=1)
    c.instruments.append(c.instruments[0].model_copy(update={'symbol':'ETHUSD'}))
    btc=rows([(100,100,99,100),(102,104,102,103),(102,104,98,100)])
    eth=rows([(100,100,99,100),(100,100,99,100),(102,104,102,103)])
    sig=signal(); sig['ETHUSD']={180:{**sig['BTCUSD'][0],'signal_time':360}}
    r=Engine(c).run({'BTCUSD':btc,'ETHUSD':eth},sig)
    assert all(t['symbol']=='BTCUSD' for t in r['trades'])
    assert [e['time'] for e in r['events']]==sorted(e['time'] for e in r['events'])
