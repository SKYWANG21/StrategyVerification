"""双均线策略 - 信号计算。

快线上穿慢线做多，快线下穿慢线做空。
"""

from __future__ import annotations

from enum import IntEnum

import pandas as pd


class Signal(IntEnum):
    """信号方向。"""

    BUY = 1  # 金叉做多
    WAIT = 0  # 观望
    SELL = -1  # 死叉做空


def signal_from_cross(crossover: float) -> Signal:
    """把 Backtrader CrossOver 指标值转成信号。

    Args:
        crossover: CrossOver 指标当前值，1 表示上穿，-1 表示下穿。

    Returns:
        对应的 :class:`Signal`。
    """
    if crossover > 0:
        return Signal.BUY
    if crossover < 0:
        return Signal.SELL
    return Signal.WAIT


def generate_signals(df: pd.DataFrame, fast: int = 5, slow: int = 20) -> pd.DataFrame:
    """批量计算双均线与交叉信号。

    Args:
        df: 标准格式的 OHLCV DataFrame。
        fast: 快线周期。
        slow: 慢线周期。

    Returns:
        新增 ``ma{fast}``、``ma{slow}`` 与 ``signal`` 列的 DataFrame 副本。
    """
    result = df.copy()
    fast_col, slow_col = f"ma{fast}", f"ma{slow}"
    result[fast_col] = result["close"].rolling(window=fast, min_periods=fast).mean()
    result[slow_col] = result["close"].rolling(window=slow, min_periods=slow).mean()

    above = result[fast_col] > result[slow_col]
    result["signal"] = Signal.WAIT.value
    result.loc[above & ~above.shift(1).fillna(False), "signal"] = Signal.BUY.value
    result.loc[~above & above.shift(1).fillna(False), "signal"] = Signal.SELL.value
    return result
