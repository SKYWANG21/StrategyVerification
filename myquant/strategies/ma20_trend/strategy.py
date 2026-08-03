"""MA20 趋势跟踪策略主逻辑。

无持仓时按 :mod:`.signals` 的规则开多/开空，持仓时依次检查止损触发、
保本止损上移与反向信号平仓。仓位由基类按风险与保证金上限计算。
"""

from __future__ import annotations

from typing import Optional

import backtrader as bt

from myquant.strategies.base_strategy import BaseStrategy
from myquant.strategies.ma20_trend.risk import (
    breakeven_stop,
    calculate_stop_loss,
    is_stop_triggered,
)
from myquant.strategies.ma20_trend.signals import Signal, signal_at


class MA20TrendStrategy(BaseStrategy):
    """MA20 趋势跟踪策略。

    Attributes:
        entry_price: 当前持仓的进场价。
        stop_price: 当前持仓的止损价。
        is_long: 当前持仓是否为多头。
    """

    strategy_name = "MA20趋势跟踪"

    params = (
        ("ma_period", 20),  # 均线周期
        ("max_loss_pct", 0.06),  # 基础止损最大容忍距离
        ("force_stop_pct", 0.03),  # 强制止损比例
    )

    def __init__(self) -> None:
        """初始化均线指标与持仓状态。"""
        super().__init__()
        self.ma = bt.indicators.SimpleMovingAverage(self.data.close, period=self.p.ma_period)
        self.entry_price: Optional[float] = None
        self.stop_price: Optional[float] = None
        self.is_long: bool = True
        self._breakeven_done: bool = False

    def next(self) -> None:
        """逐 K 线驱动：有挂单则等待，无仓找机会，有仓做管理。"""
        if self.order:
            return
        if self.position:
            self._manage_position()
        else:
            self._try_entry()

    def _try_entry(self) -> None:
        """无持仓时按信号开仓。"""
        if len(self) <= self.p.ma_period:
            return

        signal = signal_at(self.data.close[0], self.data.open[0], self.ma[0])
        if signal is Signal.WAIT:
            return

        is_long = signal is Signal.BUY
        entry_price = self.data.close[0]
        prev_extreme = self.data.low[-1] if is_long else self.data.high[-1]

        stop = calculate_stop_loss(
            entry_price=entry_price,
            prev_extreme=prev_extreme,
            is_long=is_long,
            max_loss_pct=self.p.max_loss_pct,
            force_stop_pct=self.p.force_stop_pct,
        )
        size = self.size_by_risk(entry_price, stop.stop_price)
        if size <= 0:
            return

        self.entry_price = entry_price
        self.stop_price = stop.stop_price
        self.is_long = is_long
        self._breakeven_done = False
        self.order = self.buy(size=size) if is_long else self.sell(size=size)

        direction = "开多" if is_long else "开空"
        self.log(
            f"{direction} 价={entry_price:.2f} 量={size} "
            f"止损={stop.stop_price:.2f}（{stop.reason}）"
        )

    def _manage_position(self) -> None:
        """持仓期间的止损、保本与反向信号处理。"""
        if self.stop_price is None or self.entry_price is None:
            return

        if is_stop_triggered(self.data.low[0], self.data.high[0], self.stop_price, self.is_long):
            self.order = self.close()
            self.log(f"触发止损 {self.stop_price:.2f}，平仓")
            return

        if not self._breakeven_done:
            moved = breakeven_stop(self.entry_price, self.data.close[0], self.is_long)
            if moved is not None:
                self.stop_price = moved
                self._breakeven_done = True
                self.log(f"浮盈保本，止损上移至成本价 {moved:.2f}")

        signal = signal_at(self.data.close[0], self.data.open[0], self.ma[0])
        reversed_signal = Signal.SELL if self.is_long else Signal.BUY
        if signal is reversed_signal:
            self.order = self.close()
            self.log("出现反向信号，平仓")
