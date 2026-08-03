"""AKShare 数据源实现。

覆盖 A股、美股、加密货币、期货主连四类市场。各市场实际调用的 AKShare 接口名
写在 ``config/data_sources.yaml`` 的 ``sources.akshare.interfaces`` 中，
接口变动时改配置即可，无需改代码。
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Callable, Dict, Optional

import pandas as pd

from myquant.data.base_datafeed import BaseDataFeed, Market
from myquant.data.cleaner import normalize_ohlcv

logger = logging.getLogger(__name__)

# 各市场原始列名到标准列名的映射
RENAME_MAPS: Dict[Market, Dict[str, str]] = {
    Market.CN_STOCK: {
        "日期": "date",
        "开盘": "open",
        "最高": "high",
        "最低": "low",
        "收盘": "close",
        "成交量": "volume",
        "成交额": "amount",
    },
    Market.US_STOCK: {
        "日期": "date",
        "开盘": "open",
        "最高": "high",
        "最低": "low",
        "收盘": "close",
        "成交量": "volume",
        "成交额": "amount",
    },
    Market.CRYPTO: {
        "date": "date",
        "open": "open",
        "high": "high",
        "low": "low",
        "close": "close",
        "volume": "volume",
    },
    Market.FUTURES: {
        "date": "date",
        "open": "open",
        "high": "high",
        "low": "low",
        "close": "close",
        "volume": "volume",
        "hold": "open_interest",
    },
}

# 实时快照接口：市场 -> (接口名, 代码列, 最新价列)
REALTIME_SPEC: Dict[Market, tuple] = {
    Market.CN_STOCK: ("stock_zh_a_spot_em", "代码", "最新价"),
    Market.US_STOCK: ("stock_us_spot_em", "代码", "最新价"),
    Market.CRYPTO: ("crypto_js_spot", "名称", "最新价"),
}


class AkshareFeed(BaseDataFeed):
    """基于 AKShare 的数据源。"""

    name = "akshare"

    def __init__(self, config: Optional[Dict[str, Any]] = None) -> None:
        """初始化并导入 akshare。

        Args:
            config: 数据源配置，含 ``interfaces`` 与 ``adjust``。

        Raises:
            ImportError: 未安装 akshare。
        """
        super().__init__(config)
        try:
            import akshare as ak
        except ImportError as exc:
            raise ImportError("未安装 akshare，请执行 pip install akshare") from exc

        self._ak = ak
        self._interfaces: Dict[str, str] = self.config.get("interfaces", {})
        self._adjust: str = self.config.get("adjust", "qfq")
        logger.info("AKShare 数据源初始化完成")

    def get_daily(
        self,
        symbol: str,
        start: str,
        end: str,
        market: Market = Market.CN_STOCK,
    ) -> pd.DataFrame:
        """获取指定市场的历史日线。

        Args:
            symbol: 品种代码，如 ``000001``、``AAPL``、``BTC``、``RB0``。
            start: 起始日期，``YYYY-MM-DD``。
            end: 结束日期，``YYYY-MM-DD``。
            market: 市场类型。

        Returns:
            标准格式的日线 DataFrame。

        Raises:
            ValueError: 接口返回空数据。
        """
        interface = self._resolve_interface(market)
        kwargs = self._build_kwargs(symbol, start, end, market)

        logger.info("AKShare 调用 %s(%s)", self._interfaces.get(market.value), kwargs)
        raw = interface(**kwargs)

        if raw is None or raw.empty:
            raise ValueError(f"AKShare 未返回 {symbol}({market.value}) 的数据")

        return normalize_ohlcv(raw, rename_map=RENAME_MAPS[market])

    def get_realtime(self, symbol: str, market: Market = Market.CN_STOCK) -> Dict[str, Any]:
        """获取实时快照。

        Args:
            symbol: 品种代码。
            market: 市场类型。

        Returns:
            含 symbol、price、timestamp、market 的字典。

        Raises:
            NotImplementedError: 该市场暂未接入实时接口。
            ValueError: 快照表中查不到该代码。
        """
        if market not in REALTIME_SPEC:
            raise NotImplementedError(f"AKShare 实时行情暂不支持市场: {market.value}")

        func_name, symbol_col, price_col = REALTIME_SPEC[market]
        snapshot = getattr(self._ak, func_name)()
        matched = snapshot[snapshot[symbol_col].astype(str).str.contains(symbol, case=False)]

        if matched.empty:
            raise ValueError(f"实时行情中未找到 {symbol}")

        row = matched.iloc[0]
        return {
            "symbol": symbol,
            "market": market.value,
            "price": float(row[price_col]),
            "timestamp": datetime.now(),
        }

    def _resolve_interface(self, market: Market) -> Callable[..., pd.DataFrame]:
        """按配置解析该市场对应的 AKShare 接口函数。

        Args:
            market: 市场类型。

        Returns:
            AKShare 接口可调用对象。

        Raises:
            ValueError: 配置中未声明该市场的接口。
            AttributeError: 当前 akshare 版本没有该接口。
        """
        func_name = self._interfaces.get(market.value)
        if not func_name:
            raise ValueError(f"data_sources.yaml 未配置 akshare 的 {market.value} 接口")
        if not hasattr(self._ak, func_name):
            raise AttributeError(f"当前 akshare 版本无接口 {func_name}，请更新 data_sources.yaml")
        return getattr(self._ak, func_name)

    def _build_kwargs(
        self,
        symbol: str,
        start: str,
        end: str,
        market: Market,
    ) -> Dict[str, Any]:
        """构造不同市场接口所需的参数。

        期货主连接口不支持日期区间，取全量后由上层按区间过滤。

        Args:
            symbol: 品种代码。
            start: 起始日期，``YYYY-MM-DD``。
            end: 结束日期，``YYYY-MM-DD``。
            market: 市场类型。

        Returns:
            传给 AKShare 接口的关键字参数。
        """
        start_compact = start.replace("-", "")
        end_compact = end.replace("-", "")

        if market in (Market.CN_STOCK, Market.US_STOCK):
            return {
                "symbol": symbol,
                "period": "daily",
                "start_date": start_compact,
                "end_date": end_compact,
                "adjust": self._adjust,
            }
        if market is Market.CRYPTO:
            return {
                "symbol": symbol,
                "period": "day",
                "start_date": start_compact,
                "end_date": end_compact,
            }
        return {"symbol": symbol}
