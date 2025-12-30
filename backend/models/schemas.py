from pydantic import BaseModel
from typing import Optional, List


class ExecuteRequest(BaseModel):
    opportunity_id: str
    num_contracts: int


class ResetRequest(BaseModel):
    starting_balance: Optional[float] = None
