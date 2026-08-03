"""Tushare Pro 数据源实现。

覆盖 A股与期货主连，需要在环境变量 ``TUSHARE_TOKEN`` 中配置 Token。
Tushare 不提供免费的实时行情，实时相关能力请使用 AKShare 数据源。
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

import pandas as pd

from myquant.data.base_datafeed import BaseDataFeed, Market
from myquant.data.cleaner import normalize_ohlcv

logger = logging.getLogger(__name__)

# Tushare 原始列名到标准列名的映射
RENAME_MAP: Dict[str, str] = {
    "trade_date": "date",
    "vol": "volume",
    "oi": "open_interest",
}


class TushareFeed(BaseDataFeed):
    """基于 Tushare Pro 的数据源。"""

    name = "tushare"

    def __init__(self, config: Optional[Dict[str, Any]] = None) -> None:
        """初始化并校验 Token。

        Args:
            config: 数据源配置，含 ``token`` 与 ``futures_exchanges``。

        Raises:
            ImportError: 未安装 tushare。
            ValueError: Token 未配置。
        """
        super().__init__(config)
        try:
            import tushare as ts
        except ImportError as exc:
            raise ImportError("未安装 tushare，请执行 pip install tushare") from exc

        token = self.config.get("token", "")
        if not token:
            raise ValueError("Tushare token 未设置，请配置环境变量 TUSHARE_TOKEN")

        ts.set_token(token)
        self._pro = ts.pro_api()
        self._futures_exchanges: List[str] = self.config.get(
            "futures_exchanges", ["SHF", "DCE", "CZCE", "CFFEX"]
        )
        logger.info("Tushare 数据源初始化完成")

    def get_daily(
        self,
        symbol: str,
        start: str,
        end: str,
        market: Market = Market.CN_STOCK,
    ) -> pd.DataFrame:
        """获取历史日线。

        Args:
            symbol: 品种代码，如 ``000001``、``RB0``。
            start: 起始日期，``YYYY-MM-DD``。
            end: 结束日期，``YYYY-MM-DD``。
            market: 市场类型，仅支持 A股与期货。

        Returns:
            标准格式的日线 DataFrame。

        Raises:
            NotImplementedError: 传入了 Tushare 未覆盖的市场。
        """
        start_compact = start.replace("-", "")
        end_compact = end.replace("-", "")

        if market is Market.CN_STOCK:
            raw = self._fetch_stock(symbol, start_compact, end_compact)
        elif market is Market.FUTURES:
            raw = self._fetch_futures(symbol, start_compact, end_compact)
        else:
            raise NotImplementedError(f"Tushare 数据源暂不支持市场: {market.value}，请改用 akshare")

        return normalize_ohlcv(raw, rename_map=RENAME_MAP)

    def get_realtime(self, symbol: str, market: Market = Market.CN_STOCK) -> Dict[str, Any]:
        """Tushare 不提供实时行情。

        Raises:
            NotImplementedError: 始终抛出，提示改用 AKShare。
        """
        raise NotImplementedError("Tushare 不提供实时行情，请使用 --source akshare")

    def _fetch_stock(self, symbol: str, start: str, end: str) -> pd.DataFrame:
        """拉取 A股日线。

        Args:
            symbol: 股票代码，可带或不带交易所后缀。
            start: 起始日期，``YYYYMMDD``。
            end: 结束日期，``YYYYMMDD``。

        Returns:
            Tushare 原始 DataFrame。

        Raises:
            ValueError: 未取到数据。
        """
        df = self._pro.daily(ts_code=self._to_ts_code(symbol), start_date=start, end_date=end)
        if df is None or df.empty:
            raise ValueError(f"Tushare 未找到 {symbol} 的股票数据")
        return df

    def _fetch_futures(self, symbol: str, start: str, end: str) -> pd.DataFrame:
        """按交易所依次尝试拉取期货日线。

        Args:
            symbol: 期货主连代码，如 ``RB0``。
            start: 起始日期，``YYYYMMDD``。
            end: 结束日期，``YYYYMMDD``。

        Returns:
            Tushare 原始 DataFrame。

        Raises:
            ValueError: 所有交易所均未找到数据。
        """
        fields = "ts_code,trade_date,open,high,low,close,vol,oi"
        for exchange in self._futures_exchanges:
            df = self._pro.fut_daily(
                ts_code=f"{symbol}.{exchange}",
                start_date=start,
                end_date=end,
                fields=fields,
            )
            if df is not None and not df.empty:
                logger.info("在 %s 找到 %s 的期货数据", exchange, symbol)
                return df
        raise ValueError(f"Tushare 在 {self._futures_exchanges} 均未找到 {symbol} 的期货数据")

    @staticmethod
    def _to_ts_code(symbol: str) -> str:
        """把纯数字股票代码补全为 Tushare 的 ts_code。

        Args:
            symbol: 股票代码，如 ``000001`` 或 ``000001.SZ``。

        Returns:
            带交易所后缀的 ts_code。
        """
        if "." in symbol:
            return symbol
        if symbol.startswith("6"):
            return f"{symbol}.SH"
        if symbol.startswith(("4", "8")):
            return f"{symbol}.BJ"
        return f"{symbol}.SZ"
