"""端到端回测冒烟测试：模拟数据 → 引擎 → 指标 → 结果归档。"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from myquant.backtest import BacktestEngine, compare_results, format_report, save_results
from myquant.data import Market
from myquant.data.cleaner import resample_bars
from myquant.strategies import get_strategy

EXPECTED_METRIC_KEYS = {
    "total_return_pct",
    "annual_return_pct",
    "sharpe_ratio",
    "max_drawdown_pct",
    "total_trades",
    "win_rate_pct",
}


def _run(df: pd.DataFrame, strategy: str, symbol: str, market: Market):
    """在给定数据上跑一次回测。

    Args:
        df: 行情数据。
        strategy: 策略目录名。
        symbol: 品种代码。
        market: 市场类型。

    Returns:
        回测结果。
    """
    engine = BacktestEngine(symbol=symbol, market=market, initial_capital=100_000)
    return engine.run(df=df, strategy_cls=get_strategy(strategy), strategy_name=strategy)


def test_futures_backtest_produces_metrics(daily_ohlcv: pd.DataFrame) -> None:
    """期货品种在 2 日 K 线上回测应产出完整指标与净值曲线。"""
    result = _run(resample_bars(daily_ohlcv, "2D"), "ma20_trend", "RB0", Market.FUTURES)

    assert EXPECTED_METRIC_KEYS <= set(result.metrics)
    assert result.final_value > 0
    assert not result.equity_curve.empty
    assert result.metrics["total_trades"] >= 0
    assert "回 测 报 告" in format_report(result)


def test_stock_backtest_runs(daily_ohlcv: pd.DataFrame) -> None:
    """A股品种走全额保证金路径也能正常回测。"""
    result = _run(daily_ohlcv, "ma_cross", "000001", Market.CN_STOCK)

    assert result.market == "cn_stock"
    assert result.initial_capital == 100_000


def test_save_results_writes_artifacts(daily_ohlcv: pd.DataFrame, tmp_path: Path) -> None:
    """归档目录应包含摘要、交易明细与报告。"""
    result = _run(resample_bars(daily_ohlcv, "2D"), "ma20_trend", "RB0", Market.FUTURES)

    target = save_results(result, output_dir=tmp_path / result.name)

    assert (target / "summary.json").exists()
    assert (target / "trades.csv").exists()
    assert (target / "report.html").exists()

    summary = json.loads((target / "summary.json").read_text(encoding="utf-8"))
    assert summary["strategy"] == "ma20_trend"
    assert summary["symbol"] == "RB0"


def test_compare_results_sorted(daily_ohlcv: pd.DataFrame) -> None:
    """多策略对比表按总收益率降序排列。"""
    bars = resample_bars(daily_ohlcv, "2D")
    results = [
        _run(bars, "ma20_trend", "RB0", Market.FUTURES),
        _run(bars, "ma_cross", "RB0", Market.FUTURES),
    ]

    comparison = compare_results(results)

    assert list(comparison["strategy"]) == sorted(
        comparison["strategy"], key=lambda name: -comparison.set_index("strategy").loc[name, "total_return_pct"]
    )
    assert len(comparison) == 2
