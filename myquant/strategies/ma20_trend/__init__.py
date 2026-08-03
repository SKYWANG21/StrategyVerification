"""MA20 趋势跟踪策略包。

由 ``STRATEGY`` 导出策略类，供 :func:`myquant.strategies.discover_strategies` 自动发现。
"""

from myquant.strategies.ma20_trend.strategy import MA20TrendStrategy

STRATEGY = MA20TrendStrategy

__all__ = ["STRATEGY", "MA20TrendStrategy"]
