import datetime

from pydantic import TypeAdapter
from sqlalchemy import select, cast, Time, func, and_, or_, text, case, literal
from sqlalchemy.orm import joinedload, aliased

from app.config import config
from app.entity.enums import OrderType

from app.repository.base import SARepository
from app import models
from app import entity
from app.utils.datetime import utc_now



class OrderRepository(SARepository):
    model = models.Order
    schema = entity.Order
    name = "Order"

    async def get_trade_result(self, date_from: datetime.datetime) -> entity.TradeResult:
        stmt = select(
            # self.model.id,
            func.sum(self.model.price_open * self.model.value).label("spent"),
            func.sum(
                case(
                    (
                        self.model.order_type == OrderType.long,
                        case(
                            (
                                self.model.tp1_executed_at.isnot(None),
                                self.model.price_tp1 * 0.5 * self.model.value
                            ), else_=0
                        ) + case(
                            (
                                self.model.price_close.isnot(None),
                                case(
                                    (
                                        self.model.tp1_executed_at.isnot(None),
                                        0.5 * self.model.value * self.model.price_close
                                    ), else_=self.model.value * self.model.price_close
                                )
                            ), else_=0
                        )
                    ),
                    (
                        self.model.order_type == OrderType.short,
                        case(
                            (
                                self.model.tp1_executed_at.isnot(None),
                                0.5 * (2 * self.model.price_open - self.model.price_tp1) * self.model.value
                            ), else_=0
                        ) + case(
                            (
                                self.model.price_close.isnot(None),
                                case(
                                    (
                                        self.model.tp1_executed_at.isnot(None),
                                        0.5 * (2 * self.model.price_open - self.model.price_close) * self.model.value
                                    ), else_=(2 * self.model.price_open - self.model.price_close) * self.model.value
                                )
                            ), else_=0
                        )
                    ),
                    else_=0
                )
            ).label("received")
        ).filter(
            self.model.close_at >= date_from
        # ).order_by(
        #     self.model.id.asc()
        )

        result = (await self.session.execute(stmt)).one()
        return TypeAdapter(entity.TradeResult).validate_python(result)
