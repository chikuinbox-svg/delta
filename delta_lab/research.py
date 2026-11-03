from __future__ import annotations
from itertools import product
from .config import RunConfig
from .engine import Engine


def metrics(result):
    trades=result['trades']; net=[t['net_pnl'] for t in trades]
    gains=sum(p for p in net if p>0); losses=-sum(p for p in net if p<0)
    initial=result['config']['capital_inr']; peak=initial; dd=0
    for point in result['equity']:
        peak=max(peak,point['equity']); dd=max(dd,peak-point['equity'])
    return {'trades':len(trades),'net_pnl':sum(net),'win_rate':sum(p>0 for p in net)/len(net) if net else 0,
            'profit_factor':gains/losses if losses else None,'max_drawdown_inr':dd,
            'expectancy_inr':sum(net)/len(net) if net else None,
            'return_pct':(result['equity'][-1]['equity']/initial-1)*100 if result['equity'] else 0}


def compare(configs,data):
    return [{'name':c.strategy.name,'metrics':metrics(r),'result':r} for c in configs for r in [Engine(c).run(data)]]


def parameter_grid(base,grid,max_candidates=100):
    keys=list(grid)
    size=1
    for values in grid.values(): size*=len(values)
    if size<1 or size>max_candidates: raise ValueError('Grid must contain 1–100 candidates')
    configs=[]
    for values in product(*(grid[k] for k in keys)):
        raw=base.model_dump()
        for key,value in zip(keys,values):
            if key not in raw['strategy']: raise ValueError(f'Unknown strategy parameter {key}')
            raw['strategy'][key]=value
        configs.append(RunConfig.model_validate(raw))
    return configs


def walk_forward(configs,data,train_bars,test_bars,embargo_bars=10):
    """Disjoint test windows, purged order/position state, train-only selection.

    Every run starts flat and recomputes its own indicators. No warmup is borrowed
    across a boundary; this loses initial signals but avoids state contamination.
    The selected universe is fixed externally and must be audited for survivorship.
    """
    if not configs or train_bars<30 or test_bars<30 or embargo_bars<1:
        raise ValueError('Supply candidates, train/test >=30 bars and embargo >=1')
    times=sorted(set.intersection(*(set(r['time'] for r in rows) for rows in data.values()))) if data else []
    if len(times)<train_bars+embargo_bars+test_bars: raise ValueError('Not enough common history for a fold')
    def subset(a,b):
        selected=set(times[a:b])
        return {sym:[r for r in rows if r['time'] in selected] for sym,rows in data.items()}
    folds=[]
    for offset in range(0,len(times)-train_bars-embargo_bars-test_bars+1,test_bars):
        split=offset+train_bars; test_start=split+embargo_bars; test_end=test_start+test_bars
        training=compare(configs,subset(offset,split))
        # Reject no-trade candidates; net expectancy penalized by drawdown per trade.
        viable=[r for r in training if r['metrics']['trades']]
        if not viable:
            folds.append({'train_start':times[offset],'train_end':times[split-1]+180,
                          'test_start':times[test_start],'test_end':times[test_end-1]+180,'status':'no training trades; no selection'})
            continue
        best=max(viable,key=lambda r:r['metrics']['expectancy_inr']-r['metrics']['max_drawdown_inr']/r['metrics']['trades'])
        chosen=RunConfig.model_validate(best['result']['config'])
        test=Engine(chosen).run(subset(test_start,test_end))
        folds.append({'train_start':times[offset],'train_end':times[split-1]+180,
                      'test_start':times[test_start],'test_end':times[test_end-1]+180,
                      'status':'evaluated','selected_config':chosen.model_dump(),
                      'training':best['metrics'],'unseen_test':metrics(test),
                      'all_training_candidates':[{'config':r['result']['config'],'metrics':r['metrics']} for r in training],
                      'test_result':test})
    return folds
