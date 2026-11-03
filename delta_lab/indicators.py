from statistics import median


def rsi(closes, period=18):
    """Wilder RSI, seeded with period deltas; flat price = neutral 50."""
    out=[None]*len(closes)
    if len(closes)<=period: return out
    deltas=[closes[i]-closes[i-1] for i in range(1,len(closes))]
    gain=sum(max(d,0) for d in deltas[:period])/period
    loss=sum(max(-d,0) for d in deltas[:period])/period
    def value(): return 50. if gain==loss==0 else 100. if loss==0 else 100-100/(1+gain/loss)
    out[period]=value()
    for i in range(period+1,len(closes)):
        gain=(gain*(period-1)+max(deltas[i-1],0))/period
        loss=(loss*(period-1)+max(-deltas[i-1],0))/period
        out[i]=value()
    return out


def crossing(previous,current,long_threshold,short_threshold):
    if previous is None or current is None: return 0
    if previous<=long_threshold<current: return 1
    if previous>=short_threshold>current: return -1
    return 0


def relative_volume(volumes,index,lookback=20):
    if index<lookback: return None
    baseline=median(volumes[index-lookback:index])
    return volumes[index]/baseline if baseline>0 else None
