"""双均线交叉策略包。

由 ``STRATEGY`` 导出策略类，供 :func:`myquant.strategies.discover_strategies` 自动发现。
"""

from myquant.strategies.ma_cross.strategy import MACrossStrategy

STRATEGY = MACrossStrategy

__all__ = ["STRATEGY", "MACrossStrategy"]
