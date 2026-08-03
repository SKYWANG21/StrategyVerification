"""双均线交叉策略主逻辑。

金叉开多、死叉开空，止损为进场价的固定百分比，反向交叉时反手前先平仓。
主要用于验证策略插件化与多策略对比。
"""

from __future__ import annotations

from typing import Optional

import backtrader as bt

from myquant.strategies.base_strategy import BaseStrategy
from myquant.strategies.ma_cross.signals import Signal, signal_from_cross


class MACrossStrategy(BaseStrategy):
    """双均线交叉策略。"""

    strategy_name = "双均线交叉"

    params = (
        ("fast", 5),  # 快线周期
        ("slow", 20),  # 慢线周期
        ("stop_pct", 0.05),  # 固定止损比例
    )

    def __init__(self) -> None:
        """初始化快慢均线与交叉指标。"""
        super().__init__()
        fast_ma = bt.indicators.SimpleMovingAverage(self.data.close, period=self.p.fast)
        slow_ma = bt.indicators.SimpleMovingAverage(self.data.close, period=self.p.slow)
        self.crossover = bt.indicators.CrossOver(fast_ma, slow_ma)
        self.stop_price: Optional[float] = None
        self.is_long: bool = True

    def next(self) -> None:
        """逐 K 线驱动：先判断离场，再判断进场。"""
        if self.order:
            return

        signal = signal_from_cross(self.crossover[0])

        if self.position:
            self._manage_position(signal)
            return
        if signal is not Signal.WAIT:
            self._enter(signal)

    def _enter(self, signal: Signal) -> None:
        """按交叉方向开仓。

        Args:
            signal: 当前交叉信号，必须为 BUY 或 SELL。
        """
        is_long = signal is Signal.BUY
        entry_price = self.data.close[0]
        stop_price = entry_price * (1 - self.p.stop_pct) if is_long else entry_price * (1 + self.p.stop_pct)

        size = self.size_by_risk(entry_price, stop_price)
        if size <= 0:
            return

        self.stop_price = stop_price
        self.is_long = is_long
        self.order = self.buy(size=size) if is_long else self.sell(size=size)
        self.log(f"{'金叉开多' if is_long else '死叉开空'} 价={entry_price:.2f} 量={size}")

    def _manage_position(self, signal: Signal) -> None:
        """持仓期间的止损与反向交叉平仓。

        Args:
            signal: 当前交叉信号。
        """
        if self.stop_price is None:
            return

        hit_stop = (
            self.data.low[0] <= self.stop_price
            if self.is_long
            else self.data.high[0] >= self.stop_price
        )
        reversed_signal = Signal.SELL if self.is_long else Signal.BUY

        if hit_stop or signal is reversed_signal:
            self.order = self.close()
            self.log("触发止损平仓" if hit_stop else "反向交叉平仓")
