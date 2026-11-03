from datetime import datetime,timezone
from zoneinfo import ZoneInfo


def diagnose(trades,data,intervals=(180,900,1800)):
    """Post-exit observations are descriptive only and never fed to signal selection."""
    result=[]
    for t in trades:
        row={**t,'entry_hour_ist':datetime.fromtimestamp(t['entry_time'],timezone.utc).astimezone(ZoneInfo('Asia/Kolkata')).hour,
             'time_to_mfe_seconds':t['mfe_time']-t['entry_time'],
             'time_to_mae_seconds':t['mae_time']-t['entry_time'],
             'failed_breakout':t['net_pnl']<0 and t['mfe_inr']<=t['fees'],
             'breakout_followthrough_inr':t['mfe_inr']}
        rows=data.get(t['symbol'],[])
        for horizon in intervals:
            # Strictly after exit bar, so ambiguous intrabar timing is never resolved with hindsight.
            future=[b for b in rows if b['time']>t['exit_time'] and b['time']+180<=t['exit_time']+horizon]
            row[f'recovery_{horizon}s_quote']=((future[-1]['close']-t['exit'])*t['direction']) if future else None
        row['descriptive_flags']=[label for condition,label in (
            (row['failed_breakout'],'limited follow-through'),
            (t['gross_pnl']>0 and t['net_pnl']<0,'costs exceed gross gain'),
            (t['reason'] in {'protective_stop','same_bar_stop'} and t['mfe_inr']>0,'positive excursion before stop'),
            (t['ambiguous'],'uncertain intrabar ordering')) if condition]
        result.append(row)
    return result
