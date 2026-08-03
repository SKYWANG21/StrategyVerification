"""可视化与报告：把回测结果落盘为图表、明细与 HTML 报告。

结果统一归档到 ``results/backtest/<策略>_<品种>_<起>_<止>/``，包含
``summary.json``、``trades.csv``、若干 PNG 图表与 ``report.html``。
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import List, Optional

import pandas as pd

from myquant.backtest.analyzer import BacktestResult
from myquant.config import get_paths

logger = logging.getLogger(__name__)


def _prepare_pyplot():
    """按无界面后端初始化 matplotlib 并配置中文字体。

    Returns:
        ``matplotlib.pyplot`` 模块；未安装 matplotlib 时返回 None。
    """
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        logger.warning("未安装 matplotlib，跳过图表生成")
        return None

    plt.rcParams["font.sans-serif"] = ["SimHei", "Microsoft YaHei", "DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False
    return plt


def plot_equity_curve(equity: pd.Series, path: Path) -> Optional[Path]:
    """绘制净值曲线。

    Args:
        equity: 以日期为索引的净值序列。
        path: 图片保存路径。

    Returns:
        实际保存路径；未生成时返回 None。
    """
    plt = _prepare_pyplot()
    if plt is None or equity.empty:
        return None

    fig, ax = plt.subplots(figsize=(12, 5))
    ax.plot(equity.index, equity.values, color="#1f77b4", linewidth=1.4)
    ax.set_title("净值曲线")
    ax.set_ylabel("账户净值")
    ax.grid(alpha=0.3)
    fig.autofmt_xdate()
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return path


def plot_drawdown(equity: pd.Series, path: Path) -> Optional[Path]:
    """绘制回撤曲线。

    Args:
        equity: 以日期为索引的净值序列。
        path: 图片保存路径。

    Returns:
        实际保存路径；未生成时返回 None。
    """
    plt = _prepare_pyplot()
    if plt is None or equity.empty:
        return None

    drawdown = (equity / equity.cummax() - 1.0) * 100

    fig, ax = plt.subplots(figsize=(12, 4))
    ax.fill_between(drawdown.index, drawdown.values, 0, color="#d62728", alpha=0.4)
    ax.set_title("回撤曲线")
    ax.set_ylabel("回撤 (%)")
    ax.grid(alpha=0.3)
    fig.autofmt_xdate()
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return path


def plot_trade_distribution(trades: pd.DataFrame, path: Path) -> Optional[Path]:
    """绘制单笔盈亏分布直方图。

    Args:
        trades: 交易明细，需含 ``pnl_comm`` 列。
        path: 图片保存路径。

    Returns:
        实际保存路径；无交易或未安装绘图库时返回 None。
    """
    plt = _prepare_pyplot()
    if plt is None or trades.empty:
        return None

    fig, ax = plt.subplots(figsize=(8, 5))
    ax.hist(trades["pnl_comm"], bins=20, color="#2ca02c", alpha=0.75)
    ax.axvline(0, color="black", linewidth=1)
    ax.set_title("单笔净盈亏分布")
    ax.set_xlabel("净盈亏")
    ax.set_ylabel("笔数")
    ax.grid(alpha=0.3)
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return path


def generate_html_report(result: BacktestResult, path: Path) -> bool:
    """用 quantstats 生成完整 HTML 绩效报告。

    Args:
        result: 回测结果。
        path: HTML 保存路径。

    Returns:
        生成成功返回 True；未安装 quantstats 或收益序列为空返回 False。
    """
    if result.returns.empty:
        return False
    try:
        import quantstats as qs
    except ImportError:
        logger.warning("未安装 quantstats，改用简版 HTML 报告")
        return False

    try:
        qs.reports.html(
            result.returns,
            output=str(path),
            title=f"{result.strategy} - {result.symbol}",
            download_filename=str(path),
        )
        return True
    except Exception as exc:  # quantstats 对短样本较敏感，失败时退回简版报告
        logger.warning("quantstats 报告生成失败，改用简版报告: %s", exc)
        return False


def write_simple_report(result: BacktestResult, path: Path, images: List[Path]) -> Path:
    """在缺少 quantstats 时生成简版 HTML 报告。

    Args:
        result: 回测结果。
        path: HTML 保存路径。
        images: 需要嵌入的图片路径列表。

    Returns:
        HTML 文件路径。
    """
    rows = "".join(
        f"<tr><td>{key}</td><td>{value:,.4f}</td></tr>"
        if isinstance(value, (int, float))
        else f"<tr><td>{key}</td><td>{value}</td></tr>"
        for key, value in result.to_summary().items()
    )
    figures = "".join(f'<img src="{img.name}" style="max-width:100%;margin:12px 0;">' for img in images)

    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<title>{result.strategy} - {result.symbol} 回测报告</title>
<style>
body {{ font-family: "Microsoft YaHei", sans-serif; margin: 32px; color: #222; }}
table {{ border-collapse: collapse; margin-bottom: 24px; }}
td {{ border: 1px solid #ddd; padding: 6px 14px; }}
td:first-child {{ background: #fafafa; font-weight: 600; }}
</style>
</head>
<body>
<h1>{result.strategy} - {result.symbol} 回测报告</h1>
<table>{rows}</table>
{figures}
</body>
</html>
"""
    path.write_text(html, encoding="utf-8")
    return path


def save_results(result: BacktestResult, output_dir: Optional[Path] = None) -> Path:
    """把一次回测的全部产出写入归档目录。

    Args:
        result: 回测结果。
        output_dir: 自定义输出目录；为 None 时按 ``results/backtest/<name>/`` 归档。

    Returns:
        归档目录路径。
    """
    target = output_dir or (get_paths()["results"] / "backtest" / result.name)
    target.mkdir(parents=True, exist_ok=True)

    (target / "summary.json").write_text(
        json.dumps(result.to_summary(), ensure_ascii=False, indent=2), encoding="utf-8"
    )
    result.trades.to_csv(target / "trades.csv", index=False, encoding="utf-8-sig")

    images = [
        image
        for image in (
            plot_equity_curve(result.equity_curve, target / "equity_curve.png"),
            plot_drawdown(result.equity_curve, target / "drawdown.png"),
            plot_trade_distribution(result.trades, target / "trade_distribution.png"),
        )
        if image is not None
    ]

    report_path = target / "report.html"
    if not generate_html_report(result, report_path):
        write_simple_report(result, report_path, images)

    logger.info("回测结果已保存到 %s", target)
    return target


def save_comparison(comparison: pd.DataFrame, name: str) -> Path:
    """保存多策略对比结果。

    Args:
        comparison: :func:`myquant.backtest.analyzer.compare_results` 的输出。
        name: 归档目录名，如 ``compare_000001_20210101_20230101``。

    Returns:
        归档目录路径。
    """
    target = get_paths()["results"] / "backtest" / name
    target.mkdir(parents=True, exist_ok=True)
    comparison.to_csv(target / "comparison.csv", index=False, encoding="utf-8-sig")
    logger.info("策略对比结果已保存到 %s", target)
    return target
