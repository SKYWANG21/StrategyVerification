"""MA20 趋势跟踪策略 - 信号计算。

规则：
- 做多：收盘价 > MA20 且 当根 K 线收阳（close > open）
- 做空：收盘价 < MA20 且 当根 K 线收阴（close < open）
- 其余情况观望

提供逐 K 线判定（回测/实盘用）与批量计算（分析、绘图用）两种接口。
"""

from __future__ import annotations

from enum import IntEnum
from typing import Optional

import pandas as pd


class Signal(IntEnum):
    """信号方向。"""

    BUY = 1  # 做多
    WAIT = 0  # 观望
    SELL = -1  # 做空


def signal_at(close: float, open_: float, ma: Optional[float]) -> Signal:
    """判定单根 K 线的信号方向。

    Args:
        close: 收盘价。
        open_: 开盘价。
        ma: 当前均线值；为 None 或 NaN 时视为均线未就绪。

    Returns:
        对应的 :class:`Signal`。
    """
    if ma is None or pd.isna(ma):
        return Signal.WAIT
    if close > ma and close > open_:
        return Signal.BUY
    if close < ma and close < open_:
        return Signal.SELL
    return Signal.WAIT


def add_ma(df: pd.DataFrame, period: int = 20, price_col: str = "close") -> pd.DataFrame:
    """添加简单移动平均列 ``ma{period}``。

    Args:
        df: 含价格列的 DataFrame。
        period: 均线周期。
        price_col: 用于计算均线的价格列名。

    Returns:
        新增均线列的 DataFrame 副本。

    Raises:
        ValueError: 价格列不存在。
    """
    if price_col not in df.columns:
        raise ValueError(f"数据中不存在列: {price_col}")

    result = df.copy()
    result[f"ma{period}"] = result[price_col].rolling(window=period, min_periods=period).mean()
    return result


def add_kline_features(df: pd.DataFrame) -> pd.DataFrame:
    """添加 K 线形态特征列。

    新增列：``is_red``（阳线）、``is_green``（阴线）、``body_size``（实体大小）、
    ``total_range``（振幅）、``body_ratio``（实体占比）。

    Args:
        df: 含 OHLC 列的 DataFrame。

    Returns:
        新增特征列的 DataFrame 副本。
    """
    result = df.copy()
    result["is_red"] = result["close"] > result["open"]
    result["is_green"] = result["close"] < result["open"]
    result["body_size"] = (result["close"] - result["open"]).abs()
    result["total_range"] = result["high"] - result["low"]
    result["body_ratio"] = result["body_size"] / result["total_range"].replace(0, pd.NA)
    return result


def generate_signals(df: pd.DataFrame, ma_period: int = 20) -> pd.DataFrame:
    """批量计算均线、K 线特征与信号列。

    Args:
        df: 标准格式的 OHLCV DataFrame。
        ma_period: 均线周期。

    Returns:
        新增 ``ma{period}``、K 线特征与 ``signal`` 列的 DataFrame 副本，
        ``signal`` 取值为 1（做多）、-1（做空）、0（观望）。
    """
    result = add_kline_features(add_ma(df, ma_period))
    ma_col = f"ma{ma_period}"

    result["signal"] = Signal.WAIT.value
    result.loc[(result["close"] > result[ma_col]) & result["is_red"], "signal"] = Signal.BUY.value
    result.loc[(result["close"] < result[ma_col]) & result["is_green"], "signal"] = Signal.SELL.value
    return result
