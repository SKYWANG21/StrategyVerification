"""实时行情流（骨架）。

复用 :meth:`myquant.data.base_datafeed.BaseDataFeed.stream_ticks` 的轮询实现，
后续阶段可扩展为 K 线聚合与 WebSocket 推送。
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Iterator

from myquant.data.base_datafeed import BaseDataFeed, Market

logger = logging.getLogger(__name__)


class DataStream:
    """把数据源的实时快照包装成可迭代的行情流。

    Attributes:
        feed: 底层数据源。
        symbol: 品种代码。
        market: 市场类型。
        interval: 轮询间隔秒数。
    """

    def __init__(
        self,
        feed: BaseDataFeed,
        symbol: str,
        market: Market = Market.CN_STOCK,
        interval: float = 3.0,
    ) -> None:
        """初始化行情流。

        Args:
            feed: 数据源实例。
            symbol: 品种代码。
            market: 市场类型。
            interval: 轮询间隔秒数。
        """
        self.feed = feed
        self.symbol = symbol
        self.market = market
        self.interval = interval

    def ticks(self) -> Iterator[Dict[str, Any]]:
        """逐条产出实时快照。

        Yields:
            含 symbol、price、timestamp 的快照字典。
        """
        logger.info("开始推送 %s 实时行情，间隔 %.1fs", self.symbol, self.interval)
        yield from self.feed.stream_ticks(self.symbol, self.market, self.interval)

    def bars(self, period: str = "1min") -> Iterator[Dict[str, Any]]:
        """把快照聚合成 K 线（待实现）。

        Args:
            period: 目标 K 线周期。

        Raises:
            NotImplementedError: K 线聚合尚未实现。
        """
        # TODO(第二阶段): 按 period 把 tick 聚合成 OHLCV bar 后推送给策略
        raise NotImplementedError("实时 K 线聚合尚未实现")
