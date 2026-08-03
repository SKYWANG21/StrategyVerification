"""回测层：引擎、绩效分析与报告输出。"""

from myquant.backtest.analyzer import BacktestResult, compare_results, format_report
from myquant.backtest.engine import BacktestEngine
from myquant.backtest.visualizer import save_comparison, save_results

__all__ = [
    "BacktestEngine",
    "BacktestResult",
    "compare_results",
    "format_report",
    "save_comparison",
    "save_results",
]
