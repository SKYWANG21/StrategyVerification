"""myquant 统一命令行入口。

支持三种模式：

- ``backtest``：单策略回测并归档报告
- ``compare``：自动发现全部策略并做横向对比
- ``live``：实盘模拟交易（第一阶段仅骨架）

示例::

    python run.py --mode backtest --strategy ma20_trend --symbol RB0 \
        --market futures --start 2024-01-01 --end 2025-12-31 --resample 2D
    python run.py --mode compare --symbol 000001 --market cn_stock
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd

# 允许以 `python myquant/run.py` 直接执行
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from myquant.backtest import (  # noqa: E402
    BacktestEngine,
    compare_results,
    format_report,
    save_comparison,
    save_results,
)
from myquant.config import get_settings, setup_logging  # noqa: E402
from myquant.data import Market, get_feed  # noqa: E402
from myquant.data.cleaner import resample_bars  # noqa: E402
from myquant.strategies import discover_strategies, get_strategy  # noqa: E402

logger = logging.getLogger(__name__)


def build_parser() -> argparse.ArgumentParser:
    """构造命令行参数解析器。

    Returns:
        已配置好全部参数的解析器。
    """
    backtest_settings = get_settings("backtest")
    parser = argparse.ArgumentParser(
        prog="run.py",
        description="myquant 量化策略研发框架统一入口",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--mode", choices=["backtest", "compare", "live"], default="backtest")
    parser.add_argument("--strategy", help="策略目录名，backtest/live 模式必填")
    parser.add_argument("--symbol", required=True, help="品种代码，如 RB0 / 000001 / AAPL / BTC")
    parser.add_argument(
        "--market",
        choices=[market.value for market in Market],
        default=Market.CN_STOCK.value,
        help="市场类型",
    )
    parser.add_argument("--start", default=backtest_settings.get("start_date"), help="起始日期")
    parser.add_argument("--end", default=backtest_settings.get("end_date"), help="结束日期")
    parser.add_argument("--source", default=None, help="数据源名称，缺省用配置中的默认源")
    parser.add_argument(
        "--capital",
        type=float,
        default=backtest_settings.get("initial_capital"),
        help="初始资金",
    )
    parser.add_argument("--resample", default=None, help="K 线重采样周期，如 2D、W")
    parser.add_argument("--no-cache", action="store_true", help="忽略本地数据缓存")
    parser.add_argument(
        "--param",
        action="append",
        default=[],
        metavar="KEY=VALUE",
        help="覆盖策略参数，可重复传入，如 --param ma_period=10",
    )
    return parser


def parse_params(pairs: List[str]) -> Dict[str, Any]:
    """把 ``key=value`` 列表解析为带类型的参数字典。

    Args:
        pairs: 形如 ``["fast=5", "stop_pct=0.03"]`` 的字符串列表。

    Returns:
        参数字典，数值与布尔值已自动转换。

    Raises:
        ValueError: 参数不含等号。
    """
    params: Dict[str, Any] = {}
    for pair in pairs:
        if "=" not in pair:
            raise ValueError(f"策略参数格式应为 KEY=VALUE，收到: {pair}")
        key, raw = pair.split("=", 1)
        params[key.strip()] = _cast_value(raw.strip())
    return params


def _cast_value(raw: str) -> Any:
    """把字符串转成 bool / int / float，无法转换时保留字符串。

    Args:
        raw: 原始字符串。

    Returns:
        转换后的值。
    """
    lowered = raw.lower()
    if lowered in ("true", "false"):
        return lowered == "true"
    for caster in (int, float):
        try:
            return caster(raw)
        except ValueError:
            continue
    return raw


def load_data(args: argparse.Namespace) -> pd.DataFrame:
    """按命令行参数拉取并预处理行情数据。

    Args:
        args: 解析后的命令行参数。

    Returns:
        标准格式的 OHLCV DataFrame，必要时已重采样。
    """
    feed = get_feed(args.source)
    market = Market(args.market)
    df = feed.fetch_daily(
        symbol=args.symbol,
        start=args.start,
        end=args.end,
        market=market,
        use_cache=not args.no_cache,
    )
    if args.resample:
        df = resample_bars(df, args.resample)
    logger.info("行情数据就绪: %d 根 K 线", len(df))
    return df


def run_backtest(args: argparse.Namespace, df: pd.DataFrame, strategy_name: str) -> Any:
    """执行单策略回测并归档结果。

    Args:
        args: 解析后的命令行参数。
        df: 行情数据。
        strategy_name: 策略目录名。

    Returns:
        回测结果对象。
    """
    engine = BacktestEngine(
        symbol=args.symbol,
        market=Market(args.market),
        initial_capital=args.capital,
    )
    result = engine.run(
        df=df,
        strategy_cls=get_strategy(strategy_name),
        strategy_name=strategy_name,
        strategy_params=parse_params(args.param),
    )
    save_results(result)
    return result


def handle_backtest(args: argparse.Namespace) -> int:
    """处理 ``--mode backtest``。

    Args:
        args: 解析后的命令行参数。

    Returns:
        进程退出码。
    """
    if not args.strategy:
        print("backtest 模式必须指定 --strategy", file=sys.stderr)
        return 2

    result = run_backtest(args, load_data(args), args.strategy)
    print(format_report(result))
    return 0


def handle_compare(args: argparse.Namespace) -> int:
    """处理 ``--mode compare``：遍历全部策略并汇总对比。

    Args:
        args: 解析后的命令行参数。

    Returns:
        进程退出码。
    """
    strategies = discover_strategies()
    if not strategies:
        print("未发现任何策略", file=sys.stderr)
        return 1

    df = load_data(args)
    results = []
    for name in sorted(strategies):
        logger.info("回测策略: %s", name)
        try:
            results.append(run_backtest(args, df, name))
        except Exception as exc:  # 单个策略失败不应中断整体对比
            logger.error("策略 %s 回测失败: %s", name, exc)

    if not results:
        print("所有策略回测均失败", file=sys.stderr)
        return 1

    comparison = compare_results(results)
    name = f"compare_{args.symbol}_{args.start.replace('-', '')}_{args.end.replace('-', '')}"
    save_comparison(comparison, name)
    print(comparison.to_string(index=False))
    return 0


def handle_live(args: argparse.Namespace) -> int:
    """处理 ``--mode live``（第一阶段未实现）。

    Args:
        args: 解析后的命令行参数。

    Returns:
        进程退出码。
    """
    from myquant.live import DataStream, LiveEngine, VirtualBroker

    feed = get_feed(args.source)
    market = Market(args.market)
    engine = LiveEngine(
        symbol=args.symbol,
        stream=DataStream(feed, args.symbol, market),
        broker=VirtualBroker(initial_cash=args.capital),
        market=market,
    )
    try:
        engine.run(get_strategy(args.strategy), parse_params(args.param))
    except NotImplementedError as exc:
        print(f"[未实现] {exc}", file=sys.stderr)
        return 3
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    """命令行主入口。

    Args:
        argv: 命令行参数列表；为 None 时取 ``sys.argv``。

    Returns:
        进程退出码。
    """
    setup_logging()
    args = build_parser().parse_args(argv)

    handlers = {
        "backtest": handle_backtest,
        "compare": handle_compare,
        "live": handle_live,
    }
    return handlers[args.mode](args)


if __name__ == "__main__":
    raise SystemExit(main())
