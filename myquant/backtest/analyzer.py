"""绩效分析：把 Backtrader 分析器结果整理成易用的指标与数据结构。"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List

import pandas as pd

logger = logging.getLogger(__name__)

TRADING_DAYS_PER_YEAR = 252


@dataclass
class BacktestResult:
    """一次回测的完整产出。

    Attributes:
        strategy: 策略名（目录名）。
        symbol: 品种代码。
        market: 市场类型。
        start: 回测起始日期。
        end: 回测结束日期。
        initial_capital: 初始资金。
        final_value: 期末净值。
        metrics: 绩效指标字典。
        trades: 平仓交易明细。
        equity_curve: 以日期为索引的净值曲线。
        returns: 以日期为索引的收益率序列。
    """

    strategy: str
    symbol: str
    market: str
    start: str
    end: str
    initial_capital: float
    final_value: float
    metrics: Dict[str, Any] = field(default_factory=dict)
    trades: pd.DataFrame = field(default_factory=pd.DataFrame)
    equity_curve: pd.Series = field(default_factory=lambda: pd.Series(dtype=float))
    returns: pd.Series = field(default_factory=lambda: pd.Series(dtype=float))

    @property
    def name(self) -> str:
        """结果归档用的唯一名称，如 ``ma20_trend_RB0_20240101_20251231``。"""
        start = self.start.replace("-", "")
        end = self.end.replace("-", "")
        safe_symbol = self.symbol.replace("/", "_")
        return f"{self.strategy}_{safe_symbol}_{start}_{end}"

    def to_summary(self) -> Dict[str, Any]:
        """导出可直接写 JSON 的摘要字典。"""
        return {
            "strategy": self.strategy,
            "symbol": self.symbol,
            "market": self.market,
            "start": self.start,
            "end": self.end,
            "initial_capital": self.initial_capital,
            "final_value": self.final_value,
            **self.metrics,
        }


def _get(analysis: Any, *keys: str, default: float = 0.0) -> Any:
    """安全地从 Backtrader 分析结果中逐层取值。

    Args:
        analysis: 分析器返回的（嵌套）字典。
        *keys: 逐层键名。
        default: 任一层缺失时的兜底值。

    Returns:
        取到的值或兜底值。
    """
    node = analysis
    for key in keys:
        if node is None or key not in node:
            return default
        node = node[key]
    return default if node is None else node


def extract_returns(strategy: Any, initial_capital: float) -> pd.Series:
    """从 TimeReturn 分析器提取按日收益率序列。

    Args:
        strategy: 回测后的策略实例。
        initial_capital: 初始资金，用于日志与校验。

    Returns:
        以日期为索引的收益率 Series；无数据时返回空 Series。
    """
    raw = strategy.analyzers.timereturn.get_analysis()
    if not raw:
        logger.warning("TimeReturn 分析器无数据，初始资金 %.2f", initial_capital)
        return pd.Series(dtype=float)

    series = pd.Series(raw, dtype=float)
    series.index = pd.to_datetime(list(raw.keys()))
    series.index.name = "date"
    return series.sort_index()


def build_equity_curve(returns: pd.Series, initial_capital: float) -> pd.Series:
    """按收益率序列还原净值曲线。

    Args:
        returns: 按日收益率序列。
        initial_capital: 初始资金。

    Returns:
        以日期为索引的净值 Series。
    """
    if returns.empty:
        return pd.Series(dtype=float)
    return initial_capital * (1.0 + returns).cumprod()


def extract_trades(strategy: Any) -> pd.DataFrame:
    """把策略记录的平仓交易转成 DataFrame。

    Args:
        strategy: 回测后的策略实例。

    Returns:
        交易明细 DataFrame；无交易时返回带标准列的空表。
    """
    records: List[Dict[str, Any]] = strategy.get_trades()
    columns = ["date", "price", "size", "pnl", "pnl_comm", "bars_held"]
    if not records:
        return pd.DataFrame(columns=columns)

    trades = pd.DataFrame(records)
    trades["date"] = pd.to_datetime(trades["date"])
    return trades[columns].sort_values("date").reset_index(drop=True)


def collect_metrics(strategy: Any, initial_capital: float, final_value: float) -> Dict[str, Any]:
    """汇总收益、风险与交易三类指标。

    Args:
        strategy: 回测后的策略实例。
        initial_capital: 初始资金。
        final_value: 期末净值。

    Returns:
        指标字典，键为英文指标名，值为 float 或 int。
    """
    returns_analysis = strategy.analyzers.returns.get_analysis()
    sharpe_analysis = strategy.analyzers.sharpe.get_analysis()
    drawdown_analysis = strategy.analyzers.drawdown.get_analysis()
    trades_analysis = strategy.analyzers.trades.get_analysis()
    sqn_analysis = strategy.analyzers.sqn.get_analysis()

    total_trades = int(_get(trades_analysis, "total", "closed", default=0))
    won_trades = int(_get(trades_analysis, "won", "total", default=0))
    lost_trades = int(_get(trades_analysis, "lost", "total", default=0))
    won_pnl = float(_get(trades_analysis, "won", "pnl", "total", default=0.0))
    lost_pnl = float(_get(trades_analysis, "lost", "pnl", "total", default=0.0))

    return {
        "total_return_pct": (final_value - initial_capital) / initial_capital * 100,
        "annual_return_pct": float(_get(returns_analysis, "rnorm100", default=0.0)),
        "sharpe_ratio": float(_get(sharpe_analysis, "sharperatio", default=0.0) or 0.0),
        "max_drawdown_pct": float(_get(drawdown_analysis, "max", "drawdown", default=0.0)),
        "max_drawdown_len": int(_get(drawdown_analysis, "max", "len", default=0)),
        "sqn": float(_get(sqn_analysis, "sqn", default=0.0)),
        "total_trades": total_trades,
        "won_trades": won_trades,
        "lost_trades": lost_trades,
        "win_rate_pct": (won_trades / total_trades * 100) if total_trades else 0.0,
        "profit_factor": abs(won_pnl / lost_pnl) if lost_pnl else 0.0,
        "avg_win": float(_get(trades_analysis, "won", "pnl", "average", default=0.0)),
        "avg_loss": float(_get(trades_analysis, "lost", "pnl", "average", default=0.0)),
    }


def format_report(result: BacktestResult) -> str:
    """把回测结果渲染成控制台文本报告。

    Args:
        result: 回测结果。

    Returns:
        多行文本报告。
    """
    metrics = result.metrics
    lines = [
        "=" * 52,
        f"{'回 测 报 告':^46}",
        "=" * 52,
        f"策略: {result.strategy}    品种: {result.symbol}({result.market})",
        f"区间: {result.start} ~ {result.end}",
        f"初始资金: {result.initial_capital:,.2f}    期末净值: {result.final_value:,.2f}",
        "-" * 52,
        f"总收益率: {metrics.get('total_return_pct', 0):+.2f}%"
        f"    年化收益率: {metrics.get('annual_return_pct', 0):+.2f}%",
        f"最大回撤: {metrics.get('max_drawdown_pct', 0):.2f}%"
        f"    夏普比率: {metrics.get('sharpe_ratio', 0):.2f}",
        f"SQN: {metrics.get('sqn', 0):.2f}",
        "-" * 52,
        f"交易次数: {metrics.get('total_trades', 0)}"
        f"    胜率: {metrics.get('win_rate_pct', 0):.2f}%",
        f"盈利/亏损笔数: {metrics.get('won_trades', 0)}/{metrics.get('lost_trades', 0)}"
        f"    盈亏比: {metrics.get('profit_factor', 0):.2f}",
        f"平均盈利: {metrics.get('avg_win', 0):,.2f}    平均亏损: {metrics.get('avg_loss', 0):,.2f}",
        "=" * 52,
    ]
    return "\n".join(lines)


def compare_results(results: List[BacktestResult]) -> pd.DataFrame:
    """把多次回测结果汇总成对比表。

    Args:
        results: 回测结果列表。

    Returns:
        每行一个策略、按总收益率降序的对比 DataFrame。
    """
    if not results:
        return pd.DataFrame()

    rows = [
        {
            "strategy": result.strategy,
            "symbol": result.symbol,
            "total_return_pct": result.metrics.get("total_return_pct", 0.0),
            "annual_return_pct": result.metrics.get("annual_return_pct", 0.0),
            "max_drawdown_pct": result.metrics.get("max_drawdown_pct", 0.0),
            "sharpe_ratio": result.metrics.get("sharpe_ratio", 0.0),
            "win_rate_pct": result.metrics.get("win_rate_pct", 0.0),
            "total_trades": result.metrics.get("total_trades", 0),
        }
        for result in results
    ]
    return pd.DataFrame(rows).sort_values("total_return_pct", ascending=False).reset_index(drop=True)
