"""Deterministic, single-threaded candle simulator. No exchange execution access."""
from __future__ import annotations
from collections import defaultdict
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
import json, math
from .config import RunConfig
from .storage import quality, frame
from .strategy import signals
from .execution import tick,fill_price,fee
from .portfolio import Account

class Engine:
    def __init__(self, config: RunConfig):
        config.validate_run()
        self.config=config

    def run(self, data, signal_overrides=None):
        """signal_overrides is for deterministic tests only; dashboard always computes signals."""
        c=self.config; s=c.strategy; ex=c.execution
        specs={i.symbol:i for i in c.instruments}
        if set(data)-set(specs): raise ValueError('Missing instrument metadata')
        events=defaultdict(dict); generated={}; logs=[]; trades=[]; equity=[]
        def log(t,symbol,event,**detail): logs.append({'time':t,'symbol':symbol,'event':event,**detail})
        for symbol, rows in sorted(data.items()):
            rows=sorted(rows,key=lambda r:r['time'])
            q=quality(frame(rows),180)
            if any(q[k] for k in ('missing','duplicates','invalid','misaligned','incomplete')):
                raise ValueError(f'{symbol}: unsafe data quality {q}')
            if not rows: raise ValueError(f'{symbol}: empty history')
            generated[symbol]=signals(rows,s,specs[symbol]) if signal_overrides is None else signal_overrides.get(symbol,{})
            for row in rows: events[row['time']][symbol]=row
        if not events: raise ValueError('No candles selected')
        # Require synchronous candle coverage to avoid valuing absent markets with stale prices.
        n=len(events)
        if any(len(rows)!=n for rows in data.values()): raise ValueError('Symbols must share complete overlapping history')
        account=Account(c.capital_inr); pending={}; positions={}; last={}; sequence=0
        def unrealized():
            return sum((last[sym]-p['entry'])*p['direction']*p['quantity']*specs[sym].contract_size*specs[sym].quote_to_inr for sym,p in positions.items())
        def close(t,sym,price,reason):
            p=positions.pop(sym); inst=specs[sym]
            px=fill_price(price,p['direction'],False,ex,inst)
            exit_fee=fee(px,p['quantity'],ex,inst)
            gross=(px-p['entry'])*p['direction']*p['quantity']*inst.contract_size*inst.quote_to_inr
            account.cash+=gross-exit_fee
            account.margin-=p['margin']
            trade={**p,'symbol':sym,'exit_time':t,'exit':px,'exit_fee':exit_fee,'gross_pnl':gross,
                   'net_pnl':gross-p['entry_fee']-exit_fee-p['funding'],'reason':reason,
                   'duration_seconds':t-p['entry_time'],'fees':p['entry_fee']+exit_fee}
            trades.append(trade)
            log(t,sym,'exit',reason=reason,price=px,gross_pnl=gross,fee_inr=exit_fee,net_pnl=trade['net_pnl'])
        for idx,(t,bars) in enumerate(sorted(events.items())):
            end=t+180
            # Opening prices are the first observable prices at this timestamp.
            last.update({sym:b['open'] for sym,b in bars.items()})
            day=datetime.fromtimestamp(t,timezone.utc).astimezone(ZoneInfo('Asia/Kolkata')).date().isoformat()
            if day!=account.day:
                account.day=day; account.day_start_equity=account.cash+unrealized(); account.halted=False
                log(t,'*','new_ist_day',opening_equity=account.day_start_equity)
            opening_slots=len(positions)
            opening_available=account.available+min(0,unrealized())
            allocated_this_bar=0.
            entries_this_bar=0
            if account.cash+unrealized()<=account.day_start_equity-s.daily_loss_inr:
                account.halted=True
                for sym in list(positions): close(t,sym,last[sym],'daily_loss_at_open')
                pending.clear(); log(t,'*','daily_halt',cash=account.cash)
            disconnected=bool(ex.stress_disconnect_every and idx and idx%ex.stress_disconnect_every==0)
            if disconnected: log(t,'*','simulated_disconnect',policy='attached protective stops persist; no entries or trailing updates')
            if ex.stress_restart_every and idx and idx%ex.stress_restart_every==0:
                # Round-trip the entire mutable strategy state, including daily loss lockout.
                state=json.loads(json.dumps({'positions':positions,'pending':pending,'account':account.__dict__}))
                positions,pending=state['positions'],state['pending']; account=Account(**state['account'])
                log(t,'*','simulated_restart',policy='state serialized and restored, attached stops verified')
            for sym,p in list(positions.items()):
                b=bars[sym]; inst=specs[sym]; d=p['direction']
                funding=p['entry']*p['quantity']*inst.contract_size*inst.quote_to_inr*ex.funding_bps_per_8h/10000*(180/28800)*d
                account.cash-=funding; p['funding']+=funding
                if funding: log(end,sym,'estimated_funding',amount_inr=funding)
                # Stops active before bar processing. MFE/MAE on an exit bar are bounded by
                # observed open/exit, since ordering of its full extrema is unknowable.
                hit=b['low']<=p['stop'] if d==1 else b['high']>=p['stop']
                liquidation=p.get('liquidation')
                liq_hit=liquidation is not None and (b['low']<=liquidation if d==1 else b['high']>=liquidation)
                if hit or liq_hit:
                    reason='protective_stop'
                    level=p['stop']
                    if liq_hit and (not hit or (d==1 and liquidation>level) or (d==-1 and liquidation<level)):
                        level=liquidation; reason='estimated_liquidation'
                    price=min(b['open'],level) if d==1 else max(b['open'],level)
                    self._excursion(p,b['open'],price,end,inst)
                    p['excursion_censored']=True
                    close(t,sym,price,reason)
                else:
                    self._excursion(p,b['high'],b['low'],end,inst)
                    if not disconnected and s.trail_activation_range is not None:
                        favorable=(b['close']-p['entry'])*d
                        if favorable>=s.trail_activation_range*p['range']:
                            candidate=tick(b['close']-d*s.trail_distance_range*p['range'],inst.tick_size,d==-1)
                            updated=max(p['stop'],candidate) if d==1 else min(p['stop'],candidate)
                            if updated!=p['stop']:
                                p['stop']=updated
                                log(end,sym,'trailing_stop',stop=updated,effective='next candle',basis='completed close research rule')
            # Pending orders from prior completed bars only. Tie-breaking is deterministic symbol order.
            if not disconnected and not account.halted:
                for sym,order in sorted(list(pending.items())):
                    b=bars[sym]; inst=specs[sym]; d=order['direction']
                    if t>=order['expires']:
                        pending.pop(sym); log(t,sym,'pending_expired'); continue
                    trigger=order['trigger']
                    if not (b['high']>=trigger if d==1 else b['low']<=trigger): continue
                    if sym in positions or max(len(positions),opening_slots+entries_this_bar)>=s.max_positions:
                        log(t,sym,'entry_blocked',reason='position limit'); continue
                    pending.pop(sym)
                    base=max(b['open'],trigger) if d==1 else min(b['open'],trigger)
                    price=fill_price(base,d,True,ex,inst)
                    unit=price*inst.contract_size*inst.quote_to_inr
                    quantity=math.floor(s.notional_inr/unit/inst.lot_size)*inst.lot_size
                    if ex.estimate_partial_fills:
                        available=b['volume'] if inst.volume_unit=='contracts' else b['volume']/inst.contract_size
                        quantity=min(quantity,math.floor(available*ex.participation/inst.lot_size)*inst.lot_size)
                    if quantity<=0:
                        log(t,sym,'entry_rejected',reason='below lot size or estimated participation cap'); continue
                    entry_fee=fee(price,quantity,ex,inst)
                    margin=quantity*unit/s.leverage
                    if margin+entry_fee>min(account.available+min(0,unrealized()),opening_available-allocated_this_bar):
                        log(t,sym,'entry_rejected',reason='insufficient margin'); continue
                    distance=min(s.initial_stop_range*order['range'],s.monetary_stop_inr/(quantity*inst.contract_size*inst.quote_to_inr))
                    stop=tick(price-d*distance,inst.tick_size,d==-1)
                    touched=b['low']<=stop if d==1 else b['high']>=stop
                    ambiguous=touched and not (b['open']>=trigger if d==1 else b['open']<=trigger)
                    if ambiguous and ex.scenario=='exclude':
                        log(t,sym,'ambiguous_entry_excluded',trigger=trigger,stop=stop); continue
                    account.cash-=entry_fee; account.margin+=margin; sequence+=1
                    allocated_this_bar+=margin+entry_fee; entries_this_bar+=1
                    p={**order,'id':sequence,'entry_time':t,'entry':price,'quantity':quantity,'entry_fee':entry_fee,
                       'margin':margin,'stop':stop,'funding':0.,'mfe_inr':0.,'mae_inr':0.,'mfe_time':t,'mae_time':t,
                       'excursion_censored':True,'ambiguous':ambiguous,
                       'slippage_estimate_inr':abs(price-base)*quantity*inst.contract_size*inst.quote_to_inr}
                    if ex.maintenance_margin_pct is not None:
                        p['liquidation']=price*(1-d*(1/s.leverage-ex.maintenance_margin_pct/100))
                    positions[sym]=p
                    log(t,sym,'entry',price=price,quantity=quantity,entry_fee_inr=entry_fee,ambiguous=ambiguous,fill='estimated OHLC')
                    log(t,sym,'protective_stop_verified',stop=stop,mode='atomic simulated attachment')
                    # For an open beyond trigger, a stop touch necessarily occurs after entry.
                    if touched and (not ambiguous or ex.scenario=='conservative'):
                        close(t,sym,min(b['open'],stop) if d==1 else max(b['open'],stop),'same_bar_stop')
                    elif ambiguous:
                        log(end,sym,'optimistic_ambiguity',assumption='adverse extreme occurred before entry')
            last.update({sym:b['close'] for sym,b in bars.items()})
            if account.cash+unrealized()<=account.day_start_equity-s.daily_loss_inr:
                account.halted=True
                for sym in list(positions): close(end,sym,last[sym],'daily_loss_limit')
                pending.clear(); log(end,'*','daily_halt',cash=account.cash)
            if account.cash+unrealized()<=0:
                for sym in list(positions): close(end,sym,last[sym],'account_insolvent')
                pending.clear(); account.halted=True
            if not disconnected and not account.halted:
                for sym in sorted(bars):
                    sig=generated[sym].get(t)
                    if sig and sym not in positions:
                        inst=specs[sym]; sig=dict(sig)
                        sig['trigger']=tick(sig['trigger'],inst.tick_size,sig['direction']==1)
                        pending[sym]={**sig,'expires':end+s.expiry_bars*180}
                        log(end,sym,'pending_created',**pending[sym])
            equity.append({'time':end,'equity':account.cash+unrealized(),'cash':account.cash,'margin':account.margin,'positions':len(positions)})
        final=max(events)+180
        for sym in list(positions): close(final,sym,last[sym],'end_of_test')
        equity[-1].update(equity=account.cash,cash=account.cash,margin=0,positions=0)
        return {'trades':trades,'events':sorted(logs,key=lambda e:e['time']),'equity':equity,'config':c.model_dump(),
                'limitations':['Candle fills, costs, constant FX and funding are estimates; no exact bot replication.',
                'Entry and exit times within a candle are interval approximations; excursions on those bars are censored.',
                'Daily risk evaluated at completed closes; gap losses and costs can exceed monetary protection.',
                'Trailing uses completed-close research rule, effective next bar; Xa and bot stages are unimplemented.',
                'Current observed universe may have survivorship bias. Liquidation is a simplified scenario, not exchange margin rules.']}

    @staticmethod
    def _excursion(p,high,low,t,inst):
        d=p['direction']; multiplier=p['quantity']*inst.contract_size*inst.quote_to_inr
        favorable=max((high-p['entry'])*d,(low-p['entry'])*d)*multiplier
        adverse=min((high-p['entry'])*d,(low-p['entry'])*d)*multiplier
        if favorable>p['mfe_inr']: p['mfe_inr']=favorable; p['mfe_time']=t
        if adverse<p['mae_inr']: p['mae_inr']=adverse; p['mae_time']=t
