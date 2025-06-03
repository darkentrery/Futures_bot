from pydantic import BaseModel
from app.entity.order import Order, AddOrder


AnyModel = dict[str, any]
Entity = BaseModel
FindAllResult = tuple[int, list[Entity]]

__all__ = [
    "AnyModel",
    "Entity",
    "FindAllResult",
    "Order",
    "AddOrder",
]
