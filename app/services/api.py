import traceback
from typing import Any

from pybit.unified_trading import HTTP
from pydantic import TypeAdapter

from app import entity
from app.config import config
from app.entity.enums import OrderType
from app.logger import logger
from app.utils.datetime import utc_now


class BybitAPI:

    cli = HTTP(
        testnet=config.TESTNET,
        api_key=config.BYBIT_API_KEY,
        api_secret=config.BYBIT_API_SECRET
    )

    def __init__(self, category: str = "linear"):
        self.category = category
        self.trigger_by = "LastPrice"
        self.pair = "BTCUSDT"
        self.df_orders = []

    def create_open_order(self, order: entity.AddOrder) -> dict[str, Any]:
        ord = self.cli.place_order(
            category=self.category,
            symbol=self.pair,
            side=order.open_side,
            # orderType="Market",
            orderType="Limit",
            price=str(order.price_open),
            qty=str(order.value),
            isLeverage=1,
            positionIdx=order.position_idx,
            # triggerBy=self.trigger_by,
            # triggerDirection=1 if order.order_type == OrderType.long else 2,
            # triggerPrice=self.round_price_str(order.price_open),
        )
        logger.info(f"Create Open {order.value=} {order.price_open=}")
        return ord

    def create_close_order(self, order: entity.Order) -> dict[str, Any]:
        ord = self.cli.place_order(
            category=self.category,
            symbol=self.pair,
            side=order.close_side,
            orderType="Market",
            qty=str(0),
            isLeverage=1,
            positionIdx=order.position_idx,
            triggerBy=self.trigger_by,
            reduceOnly=True,
            closeOnTrigger=True
        )
        logger.info(f"Create Close {order.value=} {order.price_open=}")
        return ord

    # def get_position_value(self, order: Order) -> float:
    #     positions = self.cli.get_positions()
    #     for position in positions:
    #         if position["positionIdx"] == order.position_idx:
    #             return float(position["positionValue"])
    #     return 0

    def set_leverage(self, buy_leverage: float, sell_leverage: float) -> None:
        try:
            self.cli.set_leverage(
                category=self.category,
                symbol=self.pair,
                buyLeverage=str(buy_leverage),
                sellLeverage=str(sell_leverage),
            )
        except Exception as e:
            logger.error(f"{e=} {traceback.format_exc()}")

    def add_margin(self, order: entity.Order) -> None:
        kwargs = {
            "category": self.category,
            "symbol": order.pair.full_name,
            "margin": "10",
            "positionIdx": order.position_idx
        }
        self.cli._submit_request(
            method="POST",
            path=f"{self.cli.endpoint}/v5/position/add-margin",
            query=kwargs,
            auth=True,
        )

    def create_take_profit_order(self, order: entity.Order, attr: str) -> None:
        self.cli.set_trading_stop(
            category=self.category,
            symbol=self.pair,
            takeProfit=self.round_price_str(getattr(order, attr)),
            tpSize=str(order.value / 2),
            positionIdx=order.position_idx,
            tpslMode="Partial",
            tpTriggerBy=self.trigger_by,
            tpOrderType="Limit",
            tpLimitPrice=self.round_price_str(getattr(order, attr)),
        )
        logger.info(f"Create Take profit {order.price_open=} {order.value_tokens=} {getattr(order, attr)}")

    def create_stop_loss_order(self, order: entity.Order) -> None:
        self.cli.set_trading_stop(
            category=self.category,
            symbol=self.pair,
            stopLoss=self.round_price_str(order.price_sl),
            slSize=str(order.value),
            positionIdx=order.position_idx,
            # slTriggerBy=self.trigger_by,
            slTriggerBy="MarkPrice",
        )
        logger.info(f"Create Stop loss {order.value_tokens=} {order.price_sl=}")

    def cancel_order(self, order: entity.Order) -> entity.Order:
        try:
            self.cli.cancel_order(
                category=self.category,
                symbol=self.pair,
                orderId=order.orderId_open,
            )
            logger.info(f"Cancel stop {order.value_tokens=} {order.price_open=}")
        except Exception as e:
            logger.error(f"{e=} {traceback.format_exc()}")
        return order

    def get_order_history(self) -> list[dict]:
        return self.cli.get_order_history(category=self.category, symbol=self.pair)["result"]["list"]

    def get_all_orders_history(self) -> list[dict]:
        df_orders = []
        res = self.cli.get_order_history(category=self.category, limit=50)["result"]
        df_orders.extend(res["list"])
        while res["nextPageCursor"]:
            res = self.cli.get_order_history(category=self.category, limit=50, cursor=res["nextPageCursor"])["result"]
            df_orders.extend(res["list"])
        return df_orders

    def get_open_orders(self) -> list[entity.BybitOrder]:
        df_orders = []
        res = self.cli.get_open_orders(category=self.category, limit=50)["result"]
        df_orders.extend(res["list"])
        return TypeAdapter(list[entity.BybitOrder]).validate_python(df_orders)

    def get_last_orders_history(self) -> list[entity.BybitOrder]:
        df_orders = []
        res = self.cli.get_order_history(category=self.category, limit=50)["result"]
        df_orders.extend(res["list"])
        return TypeAdapter(list[entity.BybitOrder]).validate_python(df_orders)

    def get_open_orders(self) -> list[dict]:
        orders = self.cli.get_open_orders(category=self.category, symbol=self.pair)["result"]["list"]
        return TypeAdapter(list[entity.BybitOrder]).validate_python(orders)

    def get_positions(self) -> list[dict]:
        return self.cli.get_positions(category=self.category, symbol=self.pair, limit=200)["result"]["list"]

    def amend_stop_loss(self, order: entity.Order, ) -> None:
        query = {
            "category": self.category,
            "symbol": self.pair,
            "orderId": order.orderId_sl,
            # "slTriggerBy": self.setting.stop_loss_order_type,
            "triggerPrice": self.round_price_str(order.price_ts),
            # "triggerBy": self.setting.stop_loss_order_type
        }
        self.cli.amend_order(**query)

    # def amend_order(self, order: entity.Order, orderId: str, price: str, step_type: str) -> None:
    #     query = {
    #         "category": self.category,
    #         "symbol": order.pair.full_name,
    #         "orderId": orderId,
    #     }
    #     if step_type == "takeProfit":
    #         query.update({
    #             # "takeProfit": price,
    #             "tpTriggerBy": self.setting.take_profit_order_type,
    #             "triggerPrice": price,
    #             "triggerBy": self.setting.stop_loss_order_type
    #         })
    #     if step_type == "stopLoss":
    #         query.update({
    #             # "stopLoss": price,
    #             "slTriggerBy": self.setting.stop_loss_order_type,
    #             "triggerPrice": price,
    #             "triggerBy": self.setting.stop_loss_order_type
    #         })
    #
    #     self.cli.amend_order(**query)

    def get_tickers(self) -> list[dict]:
        return self.cli.get_tickers(category=self.category, symbol=self.pair)["result"]["list"]

    def get_instruments_info(self) -> list[dict]:
        return self.cli.get_instruments_info(category=self.category)["result"]["list"]

    def get_kline(self) -> list[entity.Kline]:
        raw_data = self.cli.get_kline(
            category=self.category,
            symbol=self.pair,
            interval="1",
            limit=1000
        )["result"]["list"]
        field_names = list(entity.Kline.model_fields.keys())
        klines = [entity.Kline(**dict(zip(field_names, row))) for row in raw_data]
        return klines

    def get_usdt_wallet_balance(self) -> float:
        balance = self.cli.get_wallet_balance(accountType="UNIFIED", coin="USDT")["result"]["list"]
        balance = float(balance[0]["coin"][0]["walletBalance"])
        return balance

    def round_price(self, value: float) -> float:
        return round(value, 2)

    def round_price_str(self, value: float) -> str:
        return str(self.round_price(value))
