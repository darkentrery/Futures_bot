import datetime

from pydantic import BaseModel, ConfigDict, Field


class TradeResult(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    spent: float
    received: float

    @property
    def difference(self) -> float:
        return (self.received - self.spent) #/ 10


class Kline(BaseModel):
    start: datetime.datetime
    open: float
    high: float
    low: float
    close: float
    volume: float
    turnover: float


class Ticker(BaseModel):
    close: float = Field(..., alias="lastPrice")
    mark_price: float = Field(..., alias="markPrice")
