from pydantic import BaseModel
from app.entity.order import Order, AddOrder, BybitOrder
from app.entity.trade import TradeResult, Kline, Ticker


AnyModel = dict[str, any]
Entity = BaseModel
FindAllResult = tuple[int, list[Entity]]

__all__ = [
    "AnyModel",
    "Entity",
    "FindAllResult",
    "Order",
    "AddOrder",
    "BybitOrder",
    "TradeResult",
    "Kline",
    "Ticker",
]
