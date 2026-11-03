from dataclasses import dataclass

@dataclass
class Account:
    cash: float
    margin: float = 0
    day_start_equity: float = 0
    day: str = ''
    halted: bool = False

    @property
    def available(self): return self.cash-self.margin
