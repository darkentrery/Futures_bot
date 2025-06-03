import datetime
import enum

from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.entity.enums import OrderType
# from app.entity.enums import SlotState, MeetingStatus, Ritual
from app.models.mixins import IdMixin, TimestampMixin, Base


class Order(IdMixin, TimestampMixin, Base):
    __tablename__ = "orders"

    value: Mapped[float] = mapped_column(nullable=False)
    value_tokens: Mapped[float] = mapped_column(nullable=False)
    order_type: Mapped[OrderType] = mapped_column(nullable=False)
    price_open: Mapped[float] = mapped_column(nullable=False)
    price_tp: Mapped[float] = mapped_column(nullable=False)
    price_sl: Mapped[float] = mapped_column(nullable=False)
    price_close: Mapped[float] = mapped_column(nullable=True)
    leverage: Mapped[float] = mapped_column(nullable=False)
    open_at: Mapped[datetime.datetime] = mapped_column(nullable=True)
    tp_at: Mapped[datetime.datetime] = mapped_column(nullable=True)
    sl_at: Mapped[datetime.datetime] = mapped_column(nullable=True)
    close_at: Mapped[datetime.datetime] = mapped_column(nullable=True)
    orderId_open: Mapped[str] = mapped_column(nullable=False)
    orderId_tp: Mapped[str] = mapped_column(nullable=True)
    orderId_sl: Mapped[str] = mapped_column(nullable=True)
    orderId_close: Mapped[str] = mapped_column(nullable=True)
    reverse: Mapped[bool] = mapped_column(nullable=False, default=False)
