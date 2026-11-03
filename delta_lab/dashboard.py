from __future__ import annotations
from datetime import datetime,timezone,timedelta
import json
from pathlib import Path
import polars as pl
import plotly.graph_objects as go
import plotly.express as px
import streamlit as st
from .api import PublicAPI
from .download import Downloader
from .storage import ROOT,Store,quality,atomic_json
from .config import RunConfig,Strategy,Execution,Instrument
from .engine import Engine
from .research import metrics,walk_forward,parameter_grid,compare
from .reporting import save_run,load_run
from .diagnostics import diagnose

PAGES=['Overview','Market Data','Strategy Configuration','Backtest Runner','Trade Replay','Loss Diagnosis','Strategy Comparison','Walk-Forward Research','Reports']


def chart_times(times):
    tz=st.session_state.get('display_tz','UTC')
    from zoneinfo import ZoneInfo
    return [datetime.fromtimestamp(t,timezone.utc).astimezone(ZoneInfo(tz)) for t in times]


def data_page(store):
    st.info('Public API integration is provisional until current official documentation and a real historical sample can be verified. No credentials are used.')
    if st.button('Refresh public perpetual catalogue'):
        api=PublicAPI()
        try:
            with st.spinner('Reading public catalogue…'):
                st.session_state['products']=Downloader(api,store).catalogue()
        except Exception as exc: st.error(str(exc))
        finally: api.close()
    products=st.session_state.get('products',[])
    if not products:
        path=store.root/'catalogue.jsonl'
        if path.exists():
            observations=path.read_text().splitlines()
            if observations: products=json.loads(observations[-1])['products']
    if products: st.dataframe(products)
    symbols=[p['symbol'] for p in products]
    all_markets=st.checkbox('Select all markets in observed catalogue')
    selected=st.multiselect('Markets',symbols)
    if all_markets: selected=symbols
    manual=st.text_input('Or enter a known public symbol','BTCUSD')
    resolution=st.selectbox('Candle interval',['1m','3m'])
    preset=st.selectbox('Range',['Custom','3 months','6 months','1 year'])
    now=datetime.now(timezone.utc); days={'Custom':7,'3 months':90,'6 months':180,'1 year':365}[preset]
    a,b=st.columns(2)
    start=a.date_input('Start UTC',now.date()-timedelta(days=days),key='download_start_'+preset)
    end=b.date_input('End UTC (exclusive)',now.date(),key='download_end')
    start_ts=int(datetime.combine(start,datetime.min.time(),timezone.utc).timestamp())
    end_ts=int(datetime.combine(end,datetime.min.time(),timezone.utc).timestamp())
    status=st.empty(); completed=[]
    if st.button('Download / resume',type='primary'):
        api=PublicAPI()
        try:
            for symbol in selected or [manual]:
                try:
                    Downloader(api,store).download(symbol,resolution,start_ts,end_ts,lambda p:status.json(p))
                    completed.append(symbol); st.success(f'{symbol}: requested interval complete')
                except Exception as exc: st.error(f'{symbol}: {exc}')
            st.write('Completed symbols:',completed)
        finally: api.close()
    if st.button('Inspect stored candles'):
        try:
            df=store.read(manual,resolution,start_ts,end_ts)
            st.json(quality(df,60 if resolution=='1m' else 180,start_ts,end_ts))
            st.dataframe(df); st.write('Snapshot SHA-256:',store.snapshot(manual,resolution))
            if len(df): st.write('Observed coverage UTC:',datetime.fromtimestamp(df['time'].min(),timezone.utc),datetime.fromtimestamp(df['time'].max(),timezone.utc))
        except Exception as exc: st.error(str(exc))
    st.metric('Stored Parquet bytes',sum(p.stat().st_size for p in store.root.rglob('*.parquet')))
    st.caption('Catalogue history records observations only. Delisted universe, OI, spreads, funding, depth, mark and trade history are not reconstructed. Partial or pre-listing windows remain incomplete.')


def config_page():
    current=st.session_state.get('config',RunConfig())
    s=current.strategy
    st.warning('Exact bot Xa, initial stop, trailing stages and attached-stop recovery are NOT imported. Supply only sanitized strategy excerpts for reconciliation. Never provide live credentials.')
    with st.form('strategy'):
        name=st.text_input('Strategy version name',s.name)
        a,b,c=st.columns(3)
        period=a.number_input('RSI period',2,500,s.rsi_length)
        upper=b.number_input('Long fresh cross above',1.,99.,s.long_threshold)
        lower=c.number_input('Short fresh cross below',1.,99.,s.short_threshold)
        rv=a.number_input('Relative volume / prior median',.01,100.,s.relative_volume)
        lookback=b.number_input('Volume median completed bars',2,500,s.volume_lookback)
        entry=c.number_input('Entry distance × candle range',0.,100.,s.entry_range)
        expiry=a.number_input('Pending expiry bars',1,1000,s.expiry_bars)
        turnover=b.number_input('Minimum previous 30-minute value INR',0.,1e12,s.min_30m_inr)
        turnover24=c.number_input('Minimum trailing 24h turnover INR',0.,1e14,s.min_24h_turnover_inr)
        notional=a.number_input('Notional INR / position',1.,1e9,s.notional_inr)
        leverage=b.number_input('Target leverage',1.,100.,s.leverage)
        maxpos=c.number_input('Maximum positions',1,100,s.max_positions)
        loss=a.number_input('Monetary stop distance budget INR (costs extra)',1.,1e9,s.monetary_stop_inr)
        daily=b.number_input('IST daily loss halt INR',1.,1e10,s.daily_loss_inr)
        initial=c.number_input('Research initial stop × signal range (0 = unconfirmed)',0.,100.,s.initial_stop_range or 0.)
        activation=a.number_input('Research trailing activation × range (0 = disabled)',0.,100.,s.trail_activation_range or 0.)
        distance=b.number_input('Research trailing distance × range',0.,100.,s.trail_distance_range or 0.)
        minrange=c.number_input('Minimum signal candle range %',0.,100.,s.min_range_pct)
        regime=st.selectbox('Research efficiency regime',['any','trend','range'],index=['any','trend','range'].index(s.regime))
        st.caption('Historical OI, spread and depth filters require observations unavailable in this candle-only version; setting them in JSON blocks the run rather than treating today’s values as history.')
        confirmed=st.checkbox('I confirm these explicit research alternatives; this is not an exact bot replica',s.research_rules_confirmed)
        if st.form_submit_button('Save strategy version'):
            try:
                raw=s.model_dump(); raw.update(name=name,rsi_length=period,long_threshold=upper,short_threshold=lower,
                    relative_volume=rv,volume_lookback=lookback,entry_range=entry,expiry_bars=expiry,min_30m_inr=turnover,
                    min_24h_turnover_inr=turnover24,notional_inr=notional,leverage=leverage,max_positions=maxpos,
                    monetary_stop_inr=loss,daily_loss_inr=daily,initial_stop_range=initial or None,
                    trail_activation_range=activation or None,trail_distance_range=distance or None,
                    research_rules_confirmed=confirmed,min_range_pct=minrange,regime=regime)
                updated=RunConfig.model_validate({**current.model_dump(),'strategy':raw})
                st.session_state['config']=updated
                import hashlib
                payload=updated.model_dump(); version=__import__('hashlib').sha256(json.dumps(payload,sort_keys=True).encode()).hexdigest()[:12]
                atomic_json(ROOT/'configs'/f'{version}.json',payload)
                st.success(f'Saved strategy version {version}')
            except Exception as exc: st.error(str(exc))
    files=sorted((ROOT/'configs').glob('*.json'))
    if files:
        chosen=st.selectbox('Load saved version',[p.name for p in files])
        if st.button('Load version'):
            st.session_state['config']=RunConfig.model_validate_json((ROOT/'configs'/chosen).read_text()); st.rerun()
    st.download_button('Export configuration JSON',current.model_dump_json(indent=2),'strategy.json')


def runner_page(store):
    base=st.session_state.get('config',RunConfig())
    st.info('3-minute completed candles only. Download 1-minute data for inspection; sub-bar execution and actual trade events are not implemented.')
    available=sorted(p.name for p in store.root.iterdir() if p.is_dir() and (p/'3m'/'candles.parquet').exists())
    selected=st.multiselect('Stored 3m symbols',available)
    a,b=st.columns(2)
    start=a.date_input('Backtest start UTC',datetime.now(timezone.utc).date()-timedelta(days=7))
    end=b.date_input('Backtest end UTC (exclusive)',datetime.now(timezone.utc).date())
    capital=st.number_input('Shared capital INR',1.,1e12,base.capital_inr)
    st.subheader('Verified instrument metadata')
    st.caption('Enter actual contract and tick sizes from official product documentation. FX is an explicitly constant INR conversion assumption; verify volume units. No placeholder metadata is silently accepted.')
    saved={i.symbol:i.model_dump() for i in base.instruments}
    table=[saved.get(sym,dict(symbol=sym,tick_size=0.,contract_size=0.,lot_size=1,quote_to_inr=0.,volume_unit='contracts',metadata_confirmed=False)) for sym in selected]
    edited=st.data_editor(table,key='metadata',disabled=['symbol'],column_config={'volume_unit':st.column_config.SelectboxColumn(options=['base','contracts'])}) if table else []
    st.subheader('Estimated execution scenario')
    ex=base.execution
    scenario=st.selectbox('Intrabar ordering',['conservative','optimistic','exclude'])
    fee=st.number_input('Taker fee basis points (verify actual schedule)',0.,1000.,ex.fee_bps)
    gst=st.number_input('GST % on fees (verify applicability)',0.,100.,ex.gst_pct)
    slip=st.number_input('Slippage basis points',0.,1000.,ex.slippage_bps)
    spread=st.number_input('Assumed spread basis points',0.,1000.,ex.spread_bps)
    funding=st.number_input('Estimated signed funding bps / 8h; positive = longs pay',value=ex.funding_bps_per_8h)
    partial=st.checkbox('Estimate partial fill using whole-candle volume participation',ex.estimate_partial_fills)
    participation=st.number_input('Volume participation cap',.000001,1.,ex.participation,format='%.6f')
    mm=st.number_input('Estimated maintenance margin % (0 = liquidation model disabled)',0.,99.,ex.maintenance_margin_pct or 0.)
    disconnect=st.number_input('Simulated disconnect every N bars (0 off)',0,100000,0)
    restart=st.number_input('State round-trip restart every N bars (0 off)',0,100000,0)
    acknowledge=st.checkbox('I acknowledge estimated fills, constant FX/funding, censored excursions and survivorship limitations')
    if st.button('Run paper backtest',type='primary'):
        try:
            if not selected: raise ValueError('Select stored historical symbols')
            execution=Execution(scenario=scenario,fee_bps=fee,gst_pct=gst,slippage_bps=slip,spread_bps=spread,
                funding_bps_per_8h=funding,estimate_partial_fills=partial,participation=participation,
                maintenance_margin_pct=mm or None,stress_disconnect_every=disconnect,stress_restart_every=restart,
                acknowledge_estimates=acknowledge)
            config=RunConfig(capital_inr=capital,strategy=base.strategy,execution=execution,instruments=[Instrument.model_validate(row) for row in edited])
            start_ts=int(datetime.combine(start,datetime.min.time(),timezone.utc).timestamp())
            end_ts=int(datetime.combine(end,datetime.min.time(),timezone.utc).timestamp())
            if start_ts>=end_ts: raise ValueError('Start must precede end')
            data={sym:store.read(sym,'3m',start_ts,end_ts).to_dicts() for sym in selected}
            for sym,rows in data.items():
                q=quality(__import__('delta_lab.storage',fromlist=['frame']).frame(rows),180,start_ts,end_ts)
                if any(q[k] for k in ('missing','duplicates','invalid','misaligned','incomplete')):
                    raise ValueError(f'{sym}: incomplete requested interval {q}')
            with st.spinner('Simulating chronological market events…'):
                result=Engine(config).run(data)
                folder,result=save_run(result,data,store)
            st.session_state.update(config=config,result=result,run_data=data)
            st.success(f'Saved reproducible paper simulation: {folder.name}')
            show_overview(result)
        except Exception as exc: st.error(str(exc))


def show_overview(result):
    st.caption('SIMULATED historical research performance — not live trading results')
    m=metrics(result); columns=st.columns(6)
    for col,(key,value) in zip(columns,m.items()): col.metric(key, f'{value:.3f}' if isinstance(value,float) else str(value))
    points=result['equity']
    if points:
        st.plotly_chart(go.Figure(go.Scatter(x=chart_times([p['time'] for p in points]),y=[p['equity'] for p in points],name='Simulated equity INR')),width='stretch')
    for warning in result['limitations']: st.caption(warning)


def replay(result,data):
    if not result['trades']: st.info('This run generated no trades.'); return
    index=st.selectbox('Trade',range(len(result['trades'])),format_func=lambda i:f"#{result['trades'][i]['id']} {result['trades'][i]['symbol']}")
    t=result['trades'][index]; rows=[r for r in data.get(t['symbol'],[]) if t['entry_time']-1800<=r['time']<=t['exit_time']+1800]
    if not rows: st.info('No saved input candles for this trade.'); return
    fig=go.Figure(go.Candlestick(x=chart_times([r['time'] for r in rows]),open=[r['open'] for r in rows],high=[r['high'] for r in rows],low=[r['low'] for r in rows],close=[r['close'] for r in rows],name='Historical candles'))
    fig.add_scatter(x=chart_times([t['entry_time'],t['exit_time']]),y=[t['entry'],t['exit']],mode='markers+text',text=['sim entry','sim exit'],name='Estimated fills')
    events=[e for e in result['events'] if e['symbol']==t['symbol'] and t['entry_time']<=e['time']<=t['exit_time']+180]
    stops=[e for e in events if e['event'] in {'protective_stop_verified','trailing_stop'}]
    if stops: fig.add_scatter(x=chart_times([e['time'] for e in stops]),y=[e['stop'] for e in stops],mode='lines+markers',line_shape='hv',name='Simulated stop updates')
    st.plotly_chart(fig,width='stretch'); st.json(t); st.dataframe(events)


def diagnosis_page(result,data):
    st.warning('Descriptive associations only. These charts do not demonstrate causes of losses. Entry/exit candle excursions and timing are censored by unknown intrabar order.')
    rows=diagnose(result['trades'],data)
    if not rows: st.info('No trades to diagnose.'); return
    st.dataframe(rows)
    df=pl.DataFrame(rows,infer_schema_length=None).to_pandas()
    st.plotly_chart(px.scatter(df,x='mfe_inr',y='net_pnl',color='symbol',hover_data=['reason','fees','mae_inr']),width='stretch')
    st.plotly_chart(px.scatter(df,x='relative_volume',y='net_pnl',color='symbol',title='Entry relative volume versus outcome'),width='stretch')
    st.plotly_chart(px.bar(df,x='id',y=['fees','funding','slippage_estimate_inr'],title='Estimated execution costs (slippage embedded in fills)'),width='stretch')
    st.plotly_chart(px.box(df,x='entry_hour_ist',y='net_pnl',title='Performance by IST entry hour'),width='stretch')
    st.caption('Recovery is signed price movement after exit, in quote units, without a counterfactual fill or causal claim. Missing future observations remain null.')


def research_page(data,base):
    st.warning('Universe selection may retain survivorship bias. Candidates are selected only on training data. Tests start flat, with fresh indicator warmup; test windows never overlap. Costs and execution remain estimates.')
    text=st.text_area('Strategy parameter grid JSON',json.dumps({'relative_volume':[1.5,1.8],'entry_range':[.5,1.]},indent=2))
    a,b,c=st.columns(3)
    train=a.number_input('Training bars',30,100000,480)
    test=b.number_input('Unseen test bars',30,100000,240)
    embargo=c.number_input('Embargo bars',1,1000,10)
    if st.button('Run walk-forward evaluation'):
        try:
            candidates=parameter_grid(base,json.loads(text))
            if len(candidates)*len(next(iter(data.values()),[]))>2_000_000: raise ValueError('Reduce candidate grid or history for interactive evaluation')
            with st.spinner('Evaluating disjoint chronological folds…'):
                folds=walk_forward(candidates,data,train,test,embargo)
            path=ROOT/'reports'/'walk-forward.json'; atomic_json(path,folds)
            st.json(folds); st.download_button('Download fold results',json.dumps(folds,indent=2),'walk-forward.json')
        except Exception as exc: st.error(str(exc))


def main():
    st.set_page_config(page_title='Delta Research Lab',page_icon='Δ',layout='wide')
    st.title('Delta · Research Lab')
    st.caption('Public historical data · Paper simulations · No credentials · No order execution')
    st.sidebar.selectbox('Display timezone',['UTC','Asia/Kolkata'],key='display_tz')
    page=st.sidebar.radio('Workspace',PAGES)
    store=Store(); st.header(page)
    results=sorted((ROOT/'reports').glob('*/result.json'),reverse=True)
    if results:
        chosen=st.sidebar.selectbox('Saved run',results,format_func=lambda p:p.parent.name)
        if st.sidebar.button('Load saved run'):
            result=load_run(chosen); data={}
            for sym,item in result['manifest']['snapshots'].items():
                path=chosen.parent/item['file']
                import hashlib
                if hashlib.sha256(path.read_bytes()).hexdigest()!=item['sha256']:
                    st.error('Saved input snapshot hash mismatch'); st.stop()
                data[sym]=pl.read_parquet(path).to_dicts()
            st.session_state.update(result=result,run_data=data,config=RunConfig.model_validate(result['config']))
    result=st.session_state.get('result'); data=st.session_state.get('run_data',{})
    if page=='Market Data': data_page(store)
    elif page=='Strategy Configuration': config_page()
    elif page=='Backtest Runner': runner_page(store)
    elif page=='Reports':
        if result:
            st.download_button('Export complete result, events, config and provenance',json.dumps(result,indent=2),'result.json')
            st.download_button('Export configuration',json.dumps(result['config'],indent=2),'config.json')
            if result['trades']: st.download_button('Export trades CSV',pl.DataFrame(result['trades'],infer_schema_length=None).write_csv(),'trades.csv')
            st.json(result.get('manifest',{}))
        st.markdown((ROOT/'docs'/'PROGRESS.md').read_text())
    elif not result: st.info('Download historical candles, confirm a strategy and instrument metadata, then run a paper backtest. No fictional results are displayed.')
    elif page=='Overview': show_overview(result)
    elif page=='Trade Replay': replay(result,data)
    elif page=='Loss Diagnosis': diagnosis_page(result,data)
    elif page=='Walk-Forward Research': research_page(data,RunConfig.model_validate(result['config']))
    elif page=='Strategy Comparison':
        choices=st.multiselect('Saved strategy versions',sorted((ROOT/'configs').glob('*.json')),format_func=lambda p:p.stem)
        if st.button('Compare on identical current run data'):
            try:
                base=RunConfig.model_validate(result['config']); configs=[]
                for path in choices:
                    strategy=RunConfig.model_validate_json(path.read_text()).strategy
                    configs.append(RunConfig.model_validate({**base.model_dump(),'strategy':strategy.model_dump()}))
                compared=compare(configs,data)
                st.dataframe([{'name':r['name'],**r['metrics']} for r in compared])
                atomic_json(ROOT/'reports'/'comparison.json',[{'name':r['name'],'config':r['result']['config'],'metrics':r['metrics']} for r in compared])
            except Exception as exc: st.error(str(exc))
