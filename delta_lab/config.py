from __future__ import annotations
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator

class ValidatedModel(BaseModel):
    model_config = ConfigDict(validate_default=True, extra="forbid")

class Instrument(ValidatedModel):
    symbol: str
    tick_size: float = Field(gt=0)
    contract_size: float = Field(gt=0, description='Base asset quantity per contract')
    lot_size: int = Field(default=1,gt=0)
    quote_to_inr: float = Field(gt=0, description='Explicit constant scenario assumption, not historical FX')
    volume_unit: Literal['base','contracts']
    metadata_confirmed: bool = False

class Strategy(ValidatedModel):
    name: str = 'Unreconciled research baseline'
    rsi_length: int = Field(default=18,ge=2,le=500)
    long_threshold: float = Field(default=73,gt=0,lt=100)
    short_threshold: float = Field(default=27,gt=0,lt=100)
    volume_lookback: int = Field(default=20,ge=2)
    relative_volume: float = Field(default=1.8,gt=0)
    entry_range: float = Field(default=0.5,ge=0)
    expiry_bars: int = Field(default=10,ge=1)
    min_30m_inr: float = Field(default=2_000_000,ge=0)
    notional_inr: float = Field(default=20_000,gt=0)
    leverage: float = Field(default=8,ge=1)
    max_positions: int = Field(default=4,ge=1)
    monetary_stop_inr: float = Field(default=100,gt=0)
    daily_loss_inr: float = Field(default=2500,gt=0)
    # No invented initial/trailing formula. User explicitly chooses a research alternative.
    initial_stop_range: float | None = Field(default=None,gt=0)
    trail_activation_range: float | None = Field(default=None,gt=0)
    trail_distance_range: float | None = Field(default=None,gt=0)
    research_rules_confirmed: bool = False
    min_24h_turnover_inr: float = Field(default=0,ge=0)
    min_open_interest: float | None = Field(default=None,ge=0)
    max_spread_bps: float | None = Field(default=None,ge=0)
    min_depth_inr: float | None = Field(default=None,ge=0)
    min_range_pct: float = Field(default=0,ge=0)
    max_range_pct: float | None = Field(default=None,gt=0)
    regime: Literal['any','trend','range'] = 'any'

    @model_validator(mode='after')
    def consistent(self):
        if self.short_threshold >= self.long_threshold:
            raise ValueError('Short RSI threshold must be below long threshold')
        if (self.trail_activation_range is None) != (self.trail_distance_range is None):
            raise ValueError('Supply both trailing activation and distance, or neither')
        return self

class Execution(ValidatedModel):
    scenario: Literal['conservative','optimistic','exclude'] = 'conservative'
    fee_bps: float = Field(default=5,ge=0)
    fee_role: Literal['taker','maker'] = 'taker'
    gst_pct: float = Field(default=18,ge=0)
    slippage_bps: float = Field(default=5,ge=0)
    spread_bps: float = Field(default=2,ge=0)
    funding_bps_per_8h: float = 0
    participation: float = Field(default=0.01,gt=0,le=1)
    estimate_partial_fills: bool = False
    maintenance_margin_pct: float | None = Field(default=None,ge=0,lt=100)
    stress_disconnect_every: int = Field(default=0,ge=0)
    stress_restart_every: int = Field(default=0,ge=0)
    acknowledge_estimates: bool = False

class RunConfig(ValidatedModel):
    capital_inr: float = Field(default=100_000,gt=0)
    strategy: Strategy = Field(default_factory=Strategy)
    execution: Execution = Field(default_factory=Execution)
    instruments: list[Instrument] = Field(default_factory=list)
    seed: int = 0

    def validate_run(self):
        if not self.strategy.research_rules_confirmed or self.strategy.initial_stop_range is None:
            raise ValueError('Confirm a research initial-stop rule. Exact bot Xa, attached-stop and trailing logic remain unreconciled.')
        if not self.execution.acknowledge_estimates:
            raise ValueError('Acknowledge estimated OHLC execution, costs, funding and FX assumptions')
        if not self.instruments or not all(i.metadata_confirmed for i in self.instruments):
            raise ValueError('Confirm contract sizes, tick sizes, lots, FX and candle volume units for every instrument')
        if len({i.symbol for i in self.instruments}) != len(self.instruments):
            raise ValueError('Duplicate instrument')
        if any(x is not None for x in (self.strategy.min_open_interest,self.strategy.max_spread_bps,self.strategy.min_depth_inr)):
            raise ValueError('OI/spread/depth historical filters require historical observations; candle-only runs cannot use them')
        if self.execution.fee_role == 'maker':
            raise ValueError('Breakout stop-market orders require taker assumptions; maker queue fills need quote/trade data')
