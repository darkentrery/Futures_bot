import datetime

from pydantic import BaseModel, computed_field

from app.entity.enums import OrderType
from app.entity.mixins import IdMixin, DateTimeMixin


class Order(IdMixin, DateTimeMixin):
    value: float
    value_tokens: float
    order_type: OrderType
    price_open: float
    price_tp: float
    price_sl: float
    price_close: float | None
    open_at: datetime.datetime | None
    tp_at: datetime.datetime | None
    sl_at: datetime.datetime | None
    close_at: datetime.datetime | None
    leverage: float
    orderId_open: str | None
    orderId_tp: str | None
    orderId_sl: str | None
    orderId_close: str | None
    reverse: bool

    @property
    def open_side(self) -> str:
        return "Buy" if self.order_type == OrderType.long else "Sell"

    @property
    def close_side(self) -> str:
        return "Sell" if self.order_type == OrderType.long else "Buy"

    @property
    def position_idx(self) -> int:
        return 1 if self.order_type == OrderType.long else 2


class AddOrder(BaseModel):
    order_type: OrderType
    price_open: float
    leverage: float
    orderId_open: str | None = None
    reverse: bool = False

    @property
    def open_side(self) -> str:
        return "Buy" if self.order_type == OrderType.long else "Sell"

    @property
    def close_side(self) -> str:
        return "Sell" if self.order_type == OrderType.long else "Buy"

    @property
    def position_idx(self) -> int:
        return 1 if self.order_type == OrderType.long else 2

    @computed_field
    @property
    def value_tokens(self) -> float:
        value = self.value * self.price_open
        return round(value, 2)

    @computed_field
    @property
    def value(self) -> float:
        value = self.leverage * 10 / self.price_open
        return round(value, 3)

    @computed_field
    @property
    def price_tp(self) -> float:
        percent = 0.005 if self.reverse else 0.01
        if self.order_type == OrderType.long:
            return round(self.price_open * (1 + percent), 1)
        else:
            return round(self.price_open * (1 - percent), 1)

    @computed_field
    @property
    def price_sl(self) -> float:
        percent = 0.005 if self.reverse else 0.01
        if self.order_type == OrderType.long:
            return round(self.price_open * (1 - percent), 1)
        else:
            return round(self.price_open * (1 + percent), 1)
