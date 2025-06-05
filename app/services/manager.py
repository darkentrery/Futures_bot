import asyncio
import datetime
import traceback

from pybit.exceptions import InvalidRequestError
from pydantic import TypeAdapter

from app import entity
from app.entity.enums import OrderType
from app.logger import logger
from app.repository import SAUnitOfWork
from app.services.api import BybitAPI
from app.services.direction import MultiFrameDirectionManager
from app.utils.datetime import utc_now


class Manager:
    def __init__(self, uow: SAUnitOfWork, api: BybitAPI):
        self.uow = uow
        self.api = api
        self.direction = MultiFrameDirectionManager()
        self.prices = []
        klines = self.api.get_kline()
        prices = klines[::-1]
        self.direction.load_history(prices)
        self.buy_leverage = None
        self.sell_leverage = None
        # atr = self.direction.main_tf.calculate_atr(period=10)
        # pass

    async def run(self) -> None:
        while True:
            async with self.uow:
                price = self.api.get_tickers()
                price = TypeAdapter(entity.Ticker).validate_python(price[0])
                orders = self.api.get_last_orders_history()
                open_orders = self.api.get_open_orders()
                orders = open_orders + orders
                result = await self.uow.order.get_trade_result(datetime.datetime(2025, 6, 4))
                logger.info(f"{result.spent=} {result.received=} {result.difference=}")
                self.direction.add(price)
                direction = self.direction.get_direction()
                exist_order = await self.uow.order.find_or_none({"close_at": None, "reverse": False})

                if exist_order:
                    exist_order = await self._check_order_opening(exist_order, orders, price.close, direction)
                    if not exist_order:
                        continue
                    exist_order = await self._check_order_tp_sl(exist_order, orders)
                    exist_order = await self._set_tp(exist_order, price.close)
                    exist_order = await self._set_sl(exist_order, price.close)
                    exist_order = await self._check_order_closing(exist_order, orders)
                    exist_order = await self._check_trailing_stop(exist_order)
                    exist_order = await self._check_close(exist_order, price.mark_price, direction)


                if not exist_order:
                        await self._set_open_order(price.close, direction)

                # await asyncio.sleep(0.1)

    @staticmethod
    def is_same_orders(order: entity.Order, ord: entity.BybitOrder, attr: str) -> bool:
        order_price = getattr(order, f"price_{attr}")
        if not ord.trigger_price:
            return False
        if ord.qty == order.value / 2 and ord.trigger_price == order_price:
            if attr in ["tp1", "tp2"] and ord.stop_order_type == "PartialTakeProfit":
                return True
        if (ord.qty == order.value or ord.qty == order.value / 2) and ord.trigger_price == order_price:
            if attr == "sl" and ord.stop_order_type == "StopLoss":
                return True
        return False

    def is_need_open_reverse(self, order: entity.Order, price: float) -> bool:
        if order.order_type == OrderType.long and order.price_open * 0.99 < price < order.price_open * 0.995:
            return True
        if order.order_type == OrderType.short and order.price_open * 1.005 < price < order.price_open * 1.01:
            return True
        return False

    async def _check_order_opening(
            self, order: entity.Order, orders: list[entity.BybitOrder], price: float, direction: OrderType | None
    ) -> entity.Order | None:
        """Need open uow."""
        if order.open_at is None:
            for ord in orders:
                if ord.order_id != order.orderId_open:
                    continue
                if not ord.avg_price:
                    if ord.status == "New" and (
                        (price >= order.price_open * 1.005 and order.order_type == OrderType.long) or
                        (price <= order.price_open * 0.995 and order.order_type == OrderType.short) or
                        direction != order.order_type
                    ):
                        self.api.cancel_order(order)
                        await self.uow.order.delete({"id": order.id})
                        await self.uow.commit()
                        return None
                    continue

                if ord.status == "Cancelled":
                    order = await self.uow.order.update(
                        order.id,
                        {
                            "open_at": ord.updated_at,
                            "price_open": ord.avg_price,
                            "price_close": ord.avg_price,
                            "close_at": ord.updated_at,
                            "tp1_at": ord.updated_at,
                            "tp2_at": ord.updated_at,
                            "sl_at": ord.updated_at,
                        }
                    )
                    await self.uow.commit()
                elif ord.status == "Filled":
                    order = await self.uow.order.update(order.id, {"open_at": ord.updated_at, "price_open": ord.avg_price})
                    await self.uow.commit()

        return order

    async def _check_order_tp_sl(self, order: entity.Order, orders: list[entity.BybitOrder]) -> entity.Order:
        """Need open uow."""
        update = False
        for ord in orders:
            for attr in ["tp1", "tp2", "sl"]:
                if getattr(order, f"{attr}_at") and not getattr(order, f"orderId_{attr}"):
                    if self.is_same_orders(order, ord, attr):
                        order = await self.uow.order.update(order.id, {f"orderId_{attr}": ord.order_id})
                        update = True
        if update:
            await self.uow.commit()
        return order

    async def _set_tp(self, order: entity.Order, price: float) -> entity.Order:
        params = {"tp1_at": utc_now()}
        if order.open_at and not order.orderId_tp1 and not order.tp1_at:
            if order.order_type == OrderType.long and order.price_tp1 < price:
                order.price_tp1 = price
                params["price_tp1"] = price
            if order.order_type == OrderType.short and order.price_tp1 > price:
                order.price_tp1 = price
                params["price_tp1"] = price
            try:
                self.api.create_take_profit_order(order, "price_tp1")
            except InvalidRequestError as e:
                logger.error(f"{e=} \n{traceback.format_exc()}")
                return order
            order = await self.uow.order.update(order.id, params)
            await self.uow.commit()

        params = {"tp2_at": utc_now()}
        if order.open_at and not order.orderId_tp2 and not order.tp2_at:
            if order.order_type == OrderType.long and order.price_tp2 < price:
                order.price_tp2 = price
                params["price_tp2"] = price
            if order.order_type == OrderType.short and order.price_tp2 > price:
                order.price_tp2 = price
                params["price_tp2"] = price
            try:
                self.api.create_take_profit_order(order, "price_tp2")
            except InvalidRequestError as e:
                logger.error(f"{e=} \n{traceback.format_exc()}")
                return order
            order = await self.uow.order.update(order.id, params)
            await self.uow.commit()

        return order

    async def _set_sl(self, order: entity.Order, price: float) -> entity.Order:
        params = {"sl_at": utc_now()}
        if order.open_at and not order.orderId_sl and not order.sl_at:
            if order.order_type == OrderType.long and order.price_sl > price:
                order.price_sl = price
                params["price_sl"] = price
            if order.order_type == OrderType.short and order.price_sl < price:
                order.price_sl = price
                params["price_sl"] = price

            try:
                self.api.create_stop_loss_order(order)
            except Exception as e:
                logger.error(f"{e=}\n{traceback.format_exc()}")
                return order
            order = await self.uow.order.update(order.id, params)
            await self.uow.commit()

        return order

    async def _check_order_closing(self, order: entity.Order, orders: list[entity.BybitOrder]) -> entity.Order:
        """Need open uow."""

        if (all([order.tp1_at, order.tp2_at, order.sl_at])) or (order.orderId_close and not order.close_at):
            for ord in orders:
                update = False
                if (not ord.trigger_price and not order.orderId_close) or ord.status != "Filled":
                    continue
                if order.orderId_tp1 and ord.order_id == order.orderId_tp1 and not order.tp1_executed_at:
                    order = await self.uow.order.update(
                        order.id,
                        {
                            "tp1_executed_at": ord.updated_at,
                            # "price_tp1": trigger_price
                        },
                    )
                    update = True
                if order.orderId_tp2 and ord.order_id == order.orderId_tp2 and not order.tp2_executed_at:
                    order = await self.uow.order.update(
                        order.id,
                        {
                            "close_at": ord.updated_at,
                            "orderId_close": ord.order_id,
                            "price_close": ord.avg_price,
                            "tp2_executed_at": ord.updated_at,
                            # "price_tp2": trigger_price
                        }
                    )
                    update = True
                if order.orderId_sl and ord.order_id == order.orderId_sl and not order.sl_executed_at:
                    order = await self.uow.order.update(
                        order.id, {
                            "close_at": ord.updated_at,
                            "orderId_close": ord.order_id,
                            "price_close": ord.avg_price,
                            "sl_executed_at": ord.updated_at,
                            # "price_sl": trigger_price
                        }
                    )
                    update = True
                if (order.orderId_sl and not order.sl_executed_at and ord.create_type == "CreateByStopOrder" and
                        ord.stop_order_type == "StopLoss" and ord.trigger_price == order.price_sl):
                    order = await self.uow.order.update(
                        order.id, {
                            "close_at": ord.updated_at,
                            "orderId_close": ord.order_id,
                            "price_close": ord.avg_price,
                            "sl_executed_at": ord.updated_at,
                            # "price_sl": trigger_price
                        }
                    )
                    update = True
                if order.orderId_close and ord.order_id == order.orderId_close and not order.close_at:
                    order = await self.uow.order.update(
                        order.id, {
                            "close_at": ord.updated_at,
                            # "orderId_close": ord.order_id,
                            "price_close": ord.avg_price,
                            # "sl_executed_at": ord.updated_at,
                            # "price_sl": trigger_price
                        }
                    )
                    update = True
                if update:
                    await self.uow.commit()

        return order

    async def _set_open_order(self, price: float, direction: OrderType | None) -> None:
        """Need open uow."""
        if direction in (OrderType.short, OrderType.long):
            atr = self.direction.main_tf.calculate_atr(period=14)
            if atr < price * 0.0015:
                return
            logger.info(f"Atr: {atr}")
            body = entity.AddOrder(
                order_type=direction,
                price_open=round(price, 1),
                leverage=10,
                atr=atr,
            )
            if self.buy_leverage != body.buy_leverage or self.sell_leverage != body.sell_leverage:
                self.api.set_leverage(body.buy_leverage, body.sell_leverage)
                self.buy_leverage = body.buy_leverage
                self.sell_leverage = body.sell_leverage
            try:
                order = self.api.create_open_order(body)
            except InvalidRequestError as e:
                logger.error(f"{e=}\n{traceback.format_exc()}")
                return
            body.orderId_open = order["result"]["orderId"]
            await self.uow.order.add(body.model_dump(exclude={"atr"}))
            await self.uow.commit()

    async def _check_trailing_stop(self, order: entity.Order) -> entity.Order:
        """Need open uow."""
        if order.orderId_sl and order.tp1_executed_at and (
                (order.order_type == OrderType.long and order.price_sl < order.price_open) or
                (order.order_type == OrderType.short and order.price_sl > order.price_open)
        ):
            try:
                self.api.amend_stop_loss(order)
                order = await self.uow.order.update(order.id, {"price_sl": order.price_ts})
                await self.uow.commit()
            except Exception as e:
                logger.error(f"{e=}\n{traceback.format_exc()}")
        return order

    async def _check_close(self, order: entity.Order, price: float, direction: OrderType | None) -> entity.Order:
        """Need open uow."""
        if order.close_at or not all([order.orderId_tp1, order.orderId_tp2, order.orderId_sl]):
            return order
        if (
            (order.order_type == OrderType.long and order.price_sl > price) or
            (order.order_type == OrderType.short and order.price_sl < price) or
            (order.order_type == OrderType.long and order.price_open * 0.998 > price) or
            (order.order_type == OrderType.short and order.price_open * 1.002 < price) or
            (order.tp1_executed_at and order.order_type != direction and (
                (order.order_type == OrderType.long and order.price_tp1 * 0.998 > price) or
                (order.order_type == OrderType.short and order.price_tp1 * 1.002 < price)
            ))
        ):
            try:
                ord = self.api.create_close_order(order)
            except InvalidRequestError as e:
                logger.error(f"{e=}\n{traceback.format_exc()}")
                return order
            order = await self.uow.order.update(order.id, {"orderId_close": ord["result"]["orderId"]})
            await self.uow.commit()

        return order

