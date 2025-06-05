import pandas as pd

from app import entity
from app.logger import logger
from app.entity.enums import OrderType
from app.utils.datetime import utc_now


class DirectionManager:
    def __init__(self) -> None:
        self.prices: list[entity.Kline | entity.Ticker] = []
        self.last_time = None

    def add(self, price: entity.Kline | entity.Ticker, time_key: str | None) -> None:
        now = utc_now()
        attrs = {"microsecond": 0}
        if time_key is not None:
            attrs[time_key] = 0
        minute = now.replace(**attrs)
        if minute != self.last_time:
            self.prices.append(price)
            if len(self.prices) > 200:
                self.prices.pop(0)
            self.last_time = minute

    def clear(self) -> None:
        self.prices = []

    # def _ema(self, prices: list[float], window: int) -> list[float]:
    #     ema = []
    #     multiplier = 2 / (window + 1)
    #     for i, price in enumerate(prices):
    #         if i < window - 1:
    #             ema.append(None)
    #         elif i == window - 1:
    #             sma = sum(prices[:window]) / window
    #             ema.append(sma)
    #         else:
    #             ema_value = (price - ema[-1]) * multiplier + ema[-1]
    #             ema.append(ema_value)
    #     return ema
    #
    # def _rsi(self, prices: list[float], window: int = 14) -> list[float]:
    #     gains = []
    #     losses = []
    #     rsi = []
    #
    #     for i in range(1, len(prices)):
    #         change = prices[i] - prices[i - 1]
    #         gains.append(max(change, 0))
    #         losses.append(abs(min(change, 0)))
    #
    #     for i in range(len(prices)):
    #         if i < window:
    #             rsi.append(None)
    #         elif i == window:
    #             avg_gain = sum(gains[:window]) / window
    #             avg_loss = sum(losses[:window]) / window
    #             rs = avg_gain / avg_loss if avg_loss != 0 else 0
    #             rsi.append(100 - (100 / (1 + rs)))
    #         elif i > window:
    #             gain = gains[i - 1]
    #             loss = losses[i - 1]
    #             avg_gain = ((rsi[-1] * (window - 1)) + gain) / window
    #             avg_loss = ((rsi[-1] * (window - 1)) + loss) / window
    #             rs = avg_gain / avg_loss if avg_loss != 0 else 0
    #             rsi.append(100 - (100 / (1 + rs)))
    #
    #     return rsi

    # def _rsi(self, prices: list[float], window: int = 14) -> list[float]:
    #     rsi = [None] * len(prices)
    #     if len(prices) < window + 1:
    #         return rsi
    #
    #     gains = []
    #     losses = []
    #
    #     # Первоначальные изменения
    #     for i in range(1, window + 1):
    #         change = prices[i] - prices[i - 1]
    #         gains.append(max(change, 0))
    #         losses.append(abs(min(change, 0)))
    #
    #     # Первоначальные средние значения
    #     avg_gain = sum(gains) / window
    #     avg_loss = sum(losses) / window
    #
    #     # Первая точка RSI
    #     rs = avg_gain / avg_loss if avg_loss != 0 else 0
    #     rsi[window] = 100 - (100 / (1 + rs))
    #
    #     # Последующие точки по формуле EMA
    #     for i in range(window + 1, len(prices)):
    #         change = prices[i] - prices[i - 1]
    #         gain = max(change, 0)
    #         loss = abs(min(change, 0))
    #
    #         avg_gain = (avg_gain * (window - 1) + gain) / window
    #         avg_loss = (avg_loss * (window - 1) + loss) / window
    #
    #         rs = avg_gain / avg_loss if avg_loss != 0 else 0
    #         rsi[i] = 100 - (100 / (1 + rs))
    #
    #     return rsi

    def _rsi(self, prices: list[float], window: int = 14) -> list[float]:
        series = pd.Series(prices)
        delta = series.diff()

        gain = delta.clip(lower=0)
        loss = -delta.clip(upper=0)

        avg_gain = gain.ewm(alpha=1 / window, min_periods=window).mean()
        avg_loss = loss.ewm(alpha=1 / window, min_periods=window).mean()

        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))

        return rsi.tolist()

    def _ema(self, prices: list[float], window: int) -> list[float]:
        series = pd.Series(prices)
        ema = series.ewm(span=window, adjust=False).mean()
        return ema.tolist()

    @property
    def direction(self) -> OrderType | None:
        if len(self.prices) < 100:
            return None

        prices = [kline.close for kline in self.prices]
        ema_fast = self._ema(prices, 9)
        ema_slow = self._ema(prices, 21)
        rsi = self._rsi(prices, 14)

        # Текущие значения индикаторов
        ema9 = ema_fast[-1]
        ema21 = ema_slow[-1]
        rsi_val = rsi[-1]

        volume_signal = self._volume_signal()
        logger.info(f"{volume_signal=}")

        # Условия входа
        if ema9 > ema21 and rsi_val < 70 : #and volume_signal
            return OrderType.long
        elif ema9 < ema21 and rsi_val > 30 : #and volume_signal
            return OrderType.short
        return None

    def _volume_signal(self) -> bool:
        volumes = [kline.volume for kline in self.prices if isinstance(kline, entity.Kline)]
        if len(volumes) < 20:
            return True

        series = pd.Series(volumes)
        last_volume = series.iloc[-1]
        average_volume = series.rolling(window=20).mean().iloc[-1]

        if last_volume > average_volume * 1.2:
            return True
        return False

    def load_history(self, prices: list[entity.Kline]) -> None:
        """Загружает исторические цены при старте"""
        self.prices = prices[-200:]  # максимум 100

    def calculate_true_range(self, high: float, low: float, close_prev: float) -> float:
        return max(high - low, abs(high - close_prev), abs(low - close_prev))

    def calculate_atr(self, period: int = 14) -> float | None:
        klines = [kline for kline in self.prices[:] if isinstance(kline, entity.Kline)]
        if not klines:
            return None
        trs = []
        for i in range(1, len(klines)):
            tr = self.calculate_true_range(
                klines[i].high, klines[i].low, klines[i - 1].close
            )
            trs.append(tr)
        return sum(trs[-period:]) / period if len(trs) >= period else None


class MultiFrameDirectionManager:
    def __init__(self):
        self.main_tf = DirectionManager()  # 100 минут
        self.fast_tf = DirectionManager()  # 10 минут

    def load_history(self, prices: list[entity.Kline]) -> None:
        self.main_tf.load_history(prices)

    def add(self, price: entity.Kline | entity.Ticker) -> None:
        self.main_tf.add(price, "second")
        self.fast_tf.add(price, None)

    def get_direction(self) -> OrderType | None:
        main_dir = self.main_tf.direction
        fast_dir = self.fast_tf.direction
        logger.info(f"{main_dir=}, {fast_dir=}")
        if main_dir and fast_dir == main_dir:
            return main_dir
        return None
