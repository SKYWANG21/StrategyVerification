"""数据源抽象基类。

所有数据源（AKShare、Tushare 及后续扩展）都实现 :class:`BaseDataFeed`，
向上层输出统一的 OHLCV DataFrame，使引擎层与具体数据接口解耦。
"""

from __future__ import annotations

import logging
import time
from abc import ABC, abstractmethod
from enum import Enum
from pathlib import Path
from typing import Any, Dict, Iterator, Optional

import pandas as pd

from myquant.config import get_paths
from myquant.data.cleaner import filter_date_range, normalize_ohlcv, validate_ohlcv

logger = logging.getLogger(__name__)

# 统一输出的列顺序，所有数据源必须对齐
OHLCV_COLUMNS = ["date", "open", "high", "low", "close", "volume", "open_interest"]


class Market(str, Enum):
    """支持的市场类型。"""

    CN_STOCK = "cn_stock"  # A股
    US_STOCK = "us_stock"  # 美股
    CRYPTO = "crypto"  # 加密货币
    FUTURES = "futures"  # 期货主连


class BaseDataFeed(ABC):
    """数据源抽象基类。

    子类必须实现 :meth:`get_daily` 与 :meth:`get_realtime`；
    :meth:`fetch_daily` 提供带本地缓存的模板方法，:meth:`stream_ticks` 提供默认轮询实现。

    Attributes:
        name: 数据源名称。
        config: 该数据源在 ``data_sources.yaml`` 中的配置。
    """

    name: str = "base"

    def __init__(self, config: Optional[Dict[str, Any]] = None) -> None:
        """初始化数据源。

        Args:
            config: 数据源配置，来自 :func:`myquant.config.get_data_source_config`。
        """
        self.config: Dict[str, Any] = config or {}
        self.name = str(self.config.get("name", self.name))

    @abstractmethod
    def get_daily(
        self,
        symbol: str,
        start: str,
        end: str,
        market: Market = Market.CN_STOCK,
    ) -> pd.DataFrame:
        """获取历史日线数据。

        Args:
            symbol: 品种代码。
            start: 起始日期，``YYYY-MM-DD``。
            end: 结束日期，``YYYY-MM-DD``。
            market: 市场类型。

        Returns:
            含 :data:`OHLCV_COLUMNS` 列、按日期升序的 DataFrame。

        Raises:
            ValueError: 未取到数据或市场不受支持。
        """

    @abstractmethod
    def get_realtime(self, symbol: str, market: Market = Market.CN_STOCK) -> Dict[str, Any]:
        """获取实时行情快照。

        Args:
            symbol: 品种代码。
            market: 市场类型。

        Returns:
            至少含 ``symbol``、``price``、``timestamp`` 键的字典。

        Raises:
            NotImplementedError: 该数据源不支持实时行情。
        """

    def stream_ticks(
        self,
        symbol: str,
        market: Market = Market.CN_STOCK,
        interval: float = 3.0,
    ) -> Iterator[Dict[str, Any]]:
        """以轮询方式推送实时行情。

        默认实现按固定间隔调用 :meth:`get_realtime`；若数据源提供 WebSocket，
        子类可覆盖本方法。

        Args:
            symbol: 品种代码。
            market: 市场类型。
            interval: 轮询间隔秒数。

        Yields:
            与 :meth:`get_realtime` 相同结构的快照字典。
        """
        while True:
            try:
                yield self.get_realtime(symbol, market)
            except Exception as exc:  # 单次取数失败不应中断整个行情流
                logger.warning("实时行情获取失败，%s 秒后重试: %s", interval, exc)
            time.sleep(interval)

    def fetch_daily(
        self,
        symbol: str,
        start: str,
        end: str,
        market: Market = Market.CN_STOCK,
        use_cache: bool = True,
    ) -> pd.DataFrame:
        """带本地缓存地获取日线数据。

        命中缓存时直接读 CSV，否则调用子类 :meth:`get_daily` 并写入缓存。

        Args:
            symbol: 品种代码。
            start: 起始日期，``YYYY-MM-DD``。
            end: 结束日期，``YYYY-MM-DD``。
            market: 市场类型。
            use_cache: 是否读写本地缓存。

        Returns:
            统一格式的日线 DataFrame。
        """
        cache_file = self._cache_path(symbol, start, end, market)
        if use_cache and cache_file.exists():
            df = pd.read_csv(cache_file)
            df["date"] = pd.to_datetime(df["date"])
            logger.info("命中缓存 %s（%d 条）", cache_file.name, len(df))
            return df

        df = self.get_daily(symbol, start, end, market)
        df = normalize_ohlcv(df)
        df = filter_date_range(df, start, end)
        if df.empty:
            raise ValueError(f"{self.name} 未获取到 {symbol} 在 {start}~{end} 的数据")

        for issue in validate_ohlcv(df):
            logger.warning("%s 数据校验: %s", symbol, issue)

        if use_cache:
            cache_file.parent.mkdir(parents=True, exist_ok=True)
            df.to_csv(cache_file, index=False)
            logger.info("数据已缓存到 %s", cache_file)
        return df

    def _cache_path(self, symbol: str, start: str, end: str, market: Market) -> Path:
        """生成缓存文件路径。

        Args:
            symbol: 品种代码。
            start: 起始日期。
            end: 结束日期。
            market: 市场类型。

        Returns:
            缓存 CSV 的绝对路径。
        """
        safe_symbol = symbol.replace("/", "_").replace(":", "_")
        filename = f"{self.name}_{market.value}_{safe_symbol}_{start}_{end}.csv"
        return get_paths()["cache"] / filename
