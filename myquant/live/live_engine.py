"""实盘模拟交易引擎（骨架）。

后续阶段将把 :class:`~myquant.live.virtual_broker.VirtualBroker` 与
:class:`~myquant.live.data_stream.DataStream` 注入 Backtrader 的实时运行模式，
使策略的 ``next()`` 在每根新 Bar 到达时触发，结果写入 ``results/live/``。
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional, Type

from myquant.data.base_datafeed import Market
from myquant.live.base_broker import BaseBroker
from myquant.live.data_stream import DataStream
from myquant.strategies.base_strategy import BaseStrategy

logger = logging.getLogger(__name__)


class LiveEngine:
    """实时模拟交易引擎。

    Attributes:
        symbol: 品种代码。
        market: 市场类型。
        stream: 实时行情流。
        broker: 虚拟经纪商。
    """

    def __init__(
        self,
        symbol: str,
        stream: DataStream,
        broker: BaseBroker,
        market: Market = Market.CN_STOCK,
    ) -> None:
        """初始化引擎。

        Args:
            symbol: 品种代码。
            stream: 实时行情流。
            broker: 虚拟经纪商。
            market: 市场类型。
        """
        self.symbol = symbol
        self.stream = stream
        self.broker = broker
        self.market = market

    def run(
        self,
        strategy_cls: Type[BaseStrategy],
        strategy_params: Optional[Dict[str, Any]] = None,
    ) -> None:
        """启动模拟交易（待实现）。

        Args:
            strategy_cls: 策略类。
            strategy_params: 策略参数覆盖值。

        Raises:
            NotImplementedError: 模拟交易在第一阶段仅提供接口骨架。
        """
        # TODO(第二阶段): 注入 broker 与 stream，驱动策略 next()，并落盘 results/live/
        raise NotImplementedError(
            "实盘模拟交易尚未实现，当前仅提供接口骨架；请使用 --mode backtest 或 --mode compare"
        )
