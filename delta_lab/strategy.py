from .indicators import rsi,relative_volume,crossing


def signals(rows, strategy, instrument):
    """Uses only candles up to and including a completed signal candle."""
    values=rsi([r['close'] for r in rows],strategy.rsi_length)
    volumes=[r['volume'] for r in rows]
    result={}
    for i,r in enumerate(rows):
        rv=relative_volume(volumes,i,strategy.volume_lookback)
        direction=crossing(values[i-1] if i else None,values[i],strategy.long_threshold,strategy.short_threshold)
        if not direction or rv is None or rv<strategy.relative_volume or i<9: continue
        window=rows[i-9:i+1]
        if window[-1]['time']-window[0]['time']!=9*180: continue
        multiplier=instrument.contract_size if instrument.volume_unit=='contracts' else 1
        turnover=sum(b['close']*b['volume']*multiplier*instrument.quote_to_inr for b in window)
        if turnover<strategy.min_30m_inr: continue
        if strategy.min_24h_turnover_inr:
            history=rows[max(0,i-479):i+1]
            if len(history)!=480 or history[-1]['time']-history[0]['time']!=479*180: continue
            if sum(b['close']*b['volume']*multiplier*instrument.quote_to_inr for b in history)<strategy.min_24h_turnover_inr: continue
        x=r['high']-r['low']
        pct=x/r['close']*100
        if x<=0 or pct<strategy.min_range_pct or (strategy.max_range_pct is not None and pct>strategy.max_range_pct): continue
        if strategy.regime!='any':
            if i<20: continue
            efficiency=abs(r['close']-rows[i-20]['close']) / max(sum(abs(rows[k]['close']-rows[k-1]['close']) for k in range(i-19,i+1)),1e-12)
            if (strategy.regime=='trend' and efficiency<.4) or (strategy.regime=='range' and efficiency>=.4): continue
        result[r['time']]={'direction':direction,'trigger':r['high']+strategy.entry_range*x if direction==1 else r['low']-strategy.entry_range*x,
                           'range':x,'rsi':values[i],'relative_volume':rv,'signal_time':r['time']+180}
    return result
