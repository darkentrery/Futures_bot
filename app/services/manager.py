import datetime
import traceback

from pybit.exceptions import InvalidRequestError

from app import entity
from app.entity.enums import OrderType
from app.logger import logger
from app.repository import SAUnitOfWork
from app.services.api import BybitAPI
from app.utils.datetime import utc_now


class DirectionManager:
    def __init__(self) -> None:
        self.prices = []

    def add(self, price: float) -> None:
        self.prices.append(price)
        if len(self.prices) > 3:
            del self.prices[0]

    def clear(self) -> None:
        self.prices = []

    @property
    def direction(self) -> OrderType | None:
        if len(self.prices) < 3:
            return
        up = 0
        down = 0
        for i, price in enumerate(self.prices[1:]):
            if price > self.prices[i]:
                up += 1
            if price < self.prices[i]:
                down += 1

        percent = abs((self.prices[-1] - self.prices[0]) / self.prices[0])
        logger.info(f"{self.prices} {percent=}")
        if up == len(self.prices) - 1 and percent > 0.002:
            return OrderType.long
        if down == len(self.prices) - 1 and percent > 0.002:
            return OrderType.short


class Manager:
    def __init__(self, uow: SAUnitOfWork, api: BybitAPI):
        self.uow = uow
        self.api = api
        self.direction = DirectionManager()
        self.prices = []

    async def run(self) -> None:
        while True:
            async with self.uow:
                price = self.api.get_tickers()
                price = float(price[0]["lastPrice"])
                orders = self.api.get_all_orders_history()
                # logger.info(f"price: {price}")
                self.direction.add(price)
                exist_order = await self.uow.order.find_or_none({"close_at": None, "reverse": False})
                reverse_order = await self.uow.order.find_or_none({"close_at": None, "reverse": True})

                if exist_order:
                    exist_order = await self._check_order_opening(exist_order, orders)
                    exist_order = await self._check_order_tp_sl(exist_order, orders)
                    exist_order = await self._set_tp(exist_order, price)
                    exist_order = await self._set_sl(exist_order, price)
                    exist_order = await self._check_order_closing(exist_order, orders)

                    try:
                        await self._check_create_reverse_order(exist_order, reverse_order, price)
                    except InvalidRequestError as e:
                        logger.error(traceback.format_exc())
                        continue

                if reverse_order:
                    reverse_order = await self._check_cancel_order(exist_order, reverse_order)
                    reverse_order = await self._check_order_opening(reverse_order, orders)
                    reverse_order = await self._check_order_tp_sl(reverse_order, orders)
                    reverse_order = await self._set_tp(reverse_order, price)
                    reverse_order = await self._set_sl(reverse_order, price)
                    reverse_order = await self._check_order_closing(reverse_order, orders)

                if not exist_order and not reverse_order:
                    try:
                        await self._set_open_order(price)
                    except InvalidRequestError as e:
                        logger.error(traceback.format_exc())
                        continue

                # await asyncio.sleep(0.5)

    @staticmethod
    def is_same_orders(order: entity.Order, ord: dict, attr: str) -> bool:
        order_price = getattr(order, f"price_{attr}")
        # logger.info(
        #     f"Same {order.pair_order.__str__()} {ord['stopOrderType']=} {ord['qty']=} {ord['triggerPrice']=} {order_price=} {order_qty=}"
        # )
        try:
            trigger_price = float(ord["triggerPrice"])
        except:
            return False

        if float(ord["qty"]) == order.value and trigger_price == order_price:
            if attr == "tp" and ord["stopOrderType"] == "TakeProfit":
                return True
            if attr == "sl" and ord["stopOrderType"] == "StopLoss":
                return True
        return False

    def is_need_open_reverse(self, order: entity.Order, price: float) -> bool:
        if order.order_type == OrderType.long and order.price_open * 0.99 < price < order.price_open * 0.995:
            return True
        if order.order_type == OrderType.short and order.price_open * 1.005 < price < order.price_open * 1.01:
            return True
        return False

    async def _check_order_opening(self, order: entity.Order, orders: list[dict]) -> entity.Order:
        """Need open uow."""
        if order.open_at is None:
            for ord in orders:
                if ord["orderId"] != order.orderId_open:
                    continue
                open_at = datetime.datetime.utcfromtimestamp(int(ord["createdTime"]) / 1000).replace(tzinfo=None)
                try:
                    price_on_created = float(ord["lastPriceOnCreated"])
                except:
                    continue
                if ord["orderStatus"] == "Cancelled":
                    order = await self.uow.order.update(
                        order.id,
                        {
                            "open_at": open_at,
                            "price_open": price_on_created,
                            "price_close": price_on_created,
                            "close_at": open_at,
                            "tp_at": open_at,
                            "sl_at": open_at,
                        }
                    )
                else:
                    order = await self.uow.order.update(order.id, {"open_at": open_at, "price_open": price_on_created})
                await self.uow.commit()
        return order

    async def _check_order_tp_sl(self, order: entity.Order, orders: list[dict]) -> entity.Order:
        """Need open uow."""
        update = False
        if (order.tp_at and not order.orderId_tp) or (order.sl_at and not order.orderId_sl):
            for ord in orders:
                for attr in ["tp", "sl"]:
                    if self.is_same_orders(order, ord, attr):
                        time_at = datetime.datetime.utcfromtimestamp(float(ord["createdTime"]) / 1000).replace(tzinfo=None)
                        order = await self.uow.order.update(
                            order.id, {f"orderId_{attr}": ord["orderId"]}
                        )
                        update = True
            if update:
                await self.uow.commit()
        return order

    async def _set_tp(self, order: entity.Order, price: float) -> entity.Order:
        params = {"tp_at": utc_now()}
        if order.open_at and not order.orderId_tp and not order.tp_at:
            if order.order_type == OrderType.long and order.price_tp < price:
                order.price_tp = price
                params["price_tp"] = price
            if order.order_type == OrderType.short and order.price_tp > price:
                order.price_tp = price
                params["price_tp"] = price

            self.api.create_take_profit_order(order)
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

            self.api.create_stop_loss_order(order)
            order = await self.uow.order.update(order.id, params)
            await self.uow.commit()

        return order

    async def _check_order_closing(self, order: entity.Order, orders: list[dict]) -> entity.Order:
        """Need open uow."""
        update = False
        if order.orderId_tp is not None and order.orderId_sl is not None:
            for ord in orders:
                try:
                    trigger_price = float(ord["triggerPrice"])
                except:
                    continue
                if ord["orderId"] == order.orderId_tp and ord["orderStatus"] == "Filled":
                    close_at = datetime.datetime.utcfromtimestamp(float(ord["createdTime"]) / 1000).replace(tzinfo=None)
                    order = await self.uow.order.update(
                        order.id,
                        {"close_at": close_at, "orderId_close": ord["orderId"], "price_close": float(ord["avgPrice"])}
                    )
                    update = True
                if ord["orderId"] == order.orderId_sl and ord["orderStatus"] == "Filled":
                    close_at = datetime.datetime.utcfromtimestamp(float(ord["createdTime"]) / 1000).replace(tzinfo=None)
                    order = await self.uow.order.update(
                        order.id, {"close_at": close_at, "orderId_close": ord["orderId"],
                                         "price_close": float(ord["avgPrice"])}
                    )
                    update = True
                if ord["orderStatus"] == "Filled" and ord["createType"] == "CreateByStopOrder" and ord[
                    "stopOrderType"] == "StopLoss" and trigger_price == order.price_sl:
                    close_at = datetime.datetime.utcfromtimestamp(float(ord["createdTime"]) / 1000).replace(tzinfo=None)
                    order = await self.uow.order.update(
                        order.id, {"close_at": close_at, "orderId_close": ord["orderId"],
                                         "price_close": float(ord["avgPrice"])}
                    )
                    update = True
            if update:
                await self.uow.commit()

        return order

    async def _check_create_reverse_order(
            self, order: entity.Order, reverse_order: entity.Order | None, price: float
    ) -> None:
        """Need open uow."""
        if order.tp_at and order.sl_at and reverse_order is None and self.is_need_open_reverse(order, price):
            body = entity.AddOrder(
                order_type=OrderType.long if order.order_type == OrderType.short else OrderType.short,
                price_open=round(price, 1),
                leverage=20,
                reverse=True
            )
            order = self.api.create_open_order(body)
            body.orderId_open = order["result"]["orderId"]
            await self.uow.order.add(body.model_dump())
            await self.uow.commit()

    async def _set_open_order(self, price: float) -> None:
        """Need open uow."""
        if self.direction.direction in (OrderType.short, OrderType.long):
            body = entity.AddOrder(
                order_type=self.direction.direction,
                price_open=round(price, 1),
                leverage=10
            )
            buy_leverage = body.leverage if self.direction.direction == OrderType.long else body.leverage * 2
            sell_leverage = body.leverage if self.direction.direction == OrderType.short else body.leverage * 2
            self.api.set_leverage(buy_leverage, sell_leverage)
            order = self.api.create_open_order(body)
            body.orderId_open = order["result"]["orderId"]
            await self.uow.order.add(body.model_dump())
            await self.uow.commit()

    async def _check_cancel_order(self, order: entity.Order | None, reverse_order: entity.Order) -> entity.Order | None:
        """Need open uow."""
        if not order and not reverse_order.open_at:
            await self.api.cancel_order(reverse_order)
            await self.uow.order.delete({"id": reverse_order.id})
            await self.uow.commit()
            return None
        return reverse_order
