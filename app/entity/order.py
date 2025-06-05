import datetime

from pydantic import BaseModel, computed_field, Field, field_validator

from app.entity.enums import OrderType
from app.entity.mixins import IdMixin, DateTimeMixin


class BaseOrder(BaseModel):
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

    @property
    def price_ts(self) -> float:
        percent = 0.001
        if self.order_type == OrderType.long:
            return round(self.price_open * (1 + percent), 1)
        else:
            return round(self.price_open * (1 - percent), 1)


class Order(IdMixin, DateTimeMixin, BaseOrder):
    value: float
    value_tokens: float
    # order_type: OrderType
    # price_open: float
    price_tp1: float
    price_tp2: float
    price_sl: float
    price_close: float | None
    open_at: datetime.datetime | None
    tp1_at: datetime.datetime | None
    tp2_at: datetime.datetime | None
    sl_at: datetime.datetime | None
    close_at: datetime.datetime | None
    tp1_executed_at: datetime.datetime | None
    tp2_executed_at: datetime.datetime | None
    sl_executed_at: datetime.datetime | None
    # leverage: float
    # orderId_open: str | None
    orderId_tp1: str | None
    orderId_tp2: str | None
    orderId_sl: str | None
    orderId_close: str | None
    # reverse: bool

    # @property
    # def open_side(self) -> str:
    #     return "Buy" if self.order_type == OrderType.long else "Sell"
    #
    # @property
    # def close_side(self) -> str:
    #     return "Sell" if self.order_type == OrderType.long else "Buy"
    #
    # @property
    # def position_idx(self) -> int:
    #     return 1 if self.order_type == OrderType.long else 2
    #
    # @property
    # def price_ts(self) -> float:
    #     percent = 0.001
    #     if self.order_type == OrderType.long:
    #         return round(self.price_open * (1 + percent), 1)
    #     else:
    #         return round(self.price_open * (1 - percent), 1)


class AddOrder(BaseOrder):
    # order_type: OrderType
    # price_open: float
    # leverage: float
    # orderId_open: str | None = None
    # reverse: bool = False
    atr: float

    # @property
    # def open_side(self) -> str:
    #     return "Buy" if self.order_type == OrderType.long else "Sell"
    #
    # @property
    # def close_side(self) -> str:
    #     return "Sell" if self.order_type == OrderType.long else "Buy"
    #
    # @property
    # def position_idx(self) -> int:
    #     return 1 if self.order_type == OrderType.long else 2

    @property
    def buy_leverage(self) -> float:
        return self.leverage if self.order_type == OrderType.long else self.leverage * 2

    @property
    def sell_leverage(self) -> float:
        return self.leverage if self.order_type == OrderType.short else self.leverage * 2

    @computed_field
    @property
    def value_tokens(self) -> float:
        value = self.value * self.price_open
        return round(value, 2)

    @computed_field
    @property
    def value(self) -> float:
        value_usdt = 20
        value = self.leverage * value_usdt / self.price_open
        return round(value, 3)

    @computed_field
    @property
    def price_tp1(self) -> float:
        if self.order_type == OrderType.long:
            return round(self.price_open + self.atr * 1, 1)
        else:
            return round(self.price_open - self.atr * 1, 1)

    @computed_field
    @property
    def price_tp2(self) -> float:
        if self.order_type == OrderType.long:
            return round(self.price_open + self.atr * 2.5, 1)
        else:
            return round(self.price_open - self.atr * 2.5, 1)

    @computed_field
    @property
    def price_sl(self) -> float:
        if self.order_type == OrderType.long:
            return round(self.price_open - self.atr * 1, 1)
        else:
            return round(self.price_open + self.atr * 1, 1)


class BybitOrder(BaseModel):
    order_id: str = Field(alias="orderId")
    avg_price: float | None = Field(..., alias="avgPrice")
    last_price_on_created: float = Field(..., alias="lastPriceOnCreated")
    status: str = Field(..., alias="orderStatus")
    trigger_price: float | None = Field(..., alias="triggerPrice")
    stop_order_type: str = Field(..., alias="stopOrderType")
    create_type: str = Field(..., alias="createType")
    qty: float
    created_at: datetime.datetime = Field(..., alias="createdTime")
    updated_at: datetime.datetime = Field(..., alias="updatedTime")

    @field_validator("avg_price", mode="before")
    def parse_avg_price(cls, value: str) -> float | None:
        try:
            return float(value)
        except ValueError:
            return

    @field_validator("trigger_price", mode="before")
    def parse_trigger_price(cls, value: str) -> float | None:
        try:
            return float(value)
        except ValueError:
            return

    @field_validator("created_at", mode="before")
    def parse_created_at(cls, value: str) -> datetime.datetime:
        value = datetime.datetime.utcfromtimestamp(int(value) / 1000).replace(tzinfo=None)
        return value

    @field_validator("updated_at", mode="before")
    def parse_updated_at(cls, value: str) -> datetime.datetime:
        value = datetime.datetime.utcfromtimestamp(int(value) / 1000).replace(tzinfo=None)
        return value
