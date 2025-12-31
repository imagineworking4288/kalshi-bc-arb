from pydantic import BaseModel
from typing import Optional, List


class ExecuteRequest(BaseModel):
    opportunity_id: str
    num_contracts: int


class ResetRequest(BaseModel):
    starting_balance: Optional[float] = None


class TradeRequest(BaseModel):
    ticker: str
    side: str  # 'yes' or 'no'
    action: str  # 'buy' or 'sell'
    count: int
    price_cents: int  # 1-99
    modes: List[str]  # ['paper'], ['live'], or ['paper', 'live']
