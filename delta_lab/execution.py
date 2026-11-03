from decimal import Decimal, ROUND_CEILING, ROUND_FLOOR


def tick(price, size, upward):
    p,s=Decimal(str(price)),Decimal(str(size))
    return float((p/s).to_integral_value(rounding=ROUND_CEILING if upward else ROUND_FLOOR)*s)


def fill_price(price,direction,entry,execution,instrument):
    side=direction if entry else -direction
    adjusted=price*(1+side*(execution.slippage_bps+execution.spread_bps/2)/10000)
    return tick(adjusted,instrument.tick_size,side>0)


def fee(price,quantity,execution,instrument):
    return abs(price*quantity*instrument.contract_size*instrument.quote_to_inr)*execution.fee_bps/10000*(1+execution.gst_pct/100)
