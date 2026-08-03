"""通用数据清洗工具。

与具体数据源无关的 DataFrame 处理：列名与类型统一、缺失值处理、日期过滤、
周期重采样、多品种时间对齐、价格逻辑校验。
"""

from __future__ import annotations

import logging
from typing import Dict, List, Optional

import pandas as pd

logger = logging.getLogger(__name__)

# 重采样时各列的聚合方式
AGGREGATION_RULES: Dict[str, str] = {
    "open": "first",
    "high": "max",
    "low": "min",
    "close": "last",
    "volume": "sum",
    "amount": "sum",
    "open_interest": "last",
}

_REQUIRED_COLUMNS = ["date", "open", "high", "low", "close", "volume"]


def normalize_ohlcv(
    df: pd.DataFrame,
    rename_map: Optional[Dict[str, str]] = None,
) -> pd.DataFrame:
    """把任意数据源返回的行情表统一成标准 OHLCV 格式。

    统一内容：列名重命名、date 转 datetime、价格与成交量转数值、按日期升序去重、
    补齐缺失的 ``open_interest`` 列。

    Args:
        df: 原始行情 DataFrame。
        rename_map: 原始列名到标准列名的映射，如 ``{"日期": "date"}``。

    Returns:
        含 date/open/high/low/close/volume/open_interest 列的新 DataFrame。

    Raises:
        ValueError: 重命名后仍缺少必需列。
    """
    result = df.rename(columns=rename_map) if rename_map else df.copy()

    missing = [col for col in _REQUIRED_COLUMNS if col not in result.columns]
    if missing:
        raise ValueError(f"行情数据缺少必需列: {missing}，实际列: {list(result.columns)}")

    result["date"] = pd.to_datetime(result["date"])
    for col in ["open", "high", "low", "close"]:
        result[col] = pd.to_numeric(result[col], errors="coerce")
    result["volume"] = pd.to_numeric(result["volume"], errors="coerce").fillna(0)

    if "open_interest" in result.columns:
        result["open_interest"] = pd.to_numeric(result["open_interest"], errors="coerce").fillna(0)
    else:
        result["open_interest"] = 0

    result = result.drop_duplicates(subset="date").sort_values("date").reset_index(drop=True)
    return result


def validate_ohlcv(df: pd.DataFrame, extreme_change_pct: float = 0.2) -> List[str]:
    """校验行情数据的合理性。

    Args:
        df: 标准格式的 OHLCV DataFrame。
        extreme_change_pct: 单根 K 线涨跌幅告警阈值。

    Returns:
        问题描述列表；无问题时为空列表。
    """
    issues: List[str] = []

    if df[["open", "high", "low", "close"]].isnull().any().any():
        issues.append("价格列存在缺失值")

    invalid_high = df["high"] < df[["open", "close"]].max(axis=1)
    if invalid_high.any():
        issues.append(f"{int(invalid_high.sum())} 条记录 high 低于 open/close")

    invalid_low = df["low"] > df[["open", "close"]].min(axis=1)
    if invalid_low.any():
        issues.append(f"{int(invalid_low.sum())} 条记录 low 高于 open/close")

    extreme = df["close"].pct_change().abs() > extreme_change_pct
    if extreme.any():
        issues.append(f"{int(extreme.sum())} 条记录涨跌幅超过 {extreme_change_pct:.0%}")

    return issues


def fill_missing(df: pd.DataFrame, method: str = "ffill") -> pd.DataFrame:
    """填充价格缺失值。

    Args:
        df: 标准格式的 OHLCV DataFrame。
        method: 填充方式，``ffill`` 前向填充或 ``drop`` 直接删除缺失行。

    Returns:
        处理后的新 DataFrame。

    Raises:
        ValueError: 传入了不支持的填充方式。
    """
    result = df.copy()
    price_cols = ["open", "high", "low", "close"]

    if method == "drop":
        return result.dropna(subset=price_cols).reset_index(drop=True)
    if method == "ffill":
        result[price_cols] = result[price_cols].ffill()
        return result.dropna(subset=price_cols).reset_index(drop=True)
    raise ValueError(f"不支持的缺失值处理方式: {method}")


def filter_date_range(df: pd.DataFrame, start: Optional[str], end: Optional[str]) -> pd.DataFrame:
    """按日期区间过滤行情。

    Args:
        df: 标准格式的 OHLCV DataFrame。
        start: 起始日期（含），为 None 时不限制。
        end: 结束日期（含），为 None 时不限制。

    Returns:
        过滤后的新 DataFrame。
    """
    result = df.copy()
    result["date"] = pd.to_datetime(result["date"])
    if start:
        result = result[result["date"] >= pd.to_datetime(start)]
    if end:
        result = result[result["date"] <= pd.to_datetime(end)]
    return result.reset_index(drop=True)


def resample_bars(df: pd.DataFrame, rule: str = "2D") -> pd.DataFrame:
    """把日线合成为更长周期的 K 线。

    合成规则：open 取首根、high 取最高、low 取最低、close 取末根、volume 求和。

    Args:
        df: 标准格式的 OHLCV DataFrame。
        rule: pandas 重采样规则，如 ``2D``、``W``。

    Returns:
        合成后的 DataFrame，已剔除节假日产生的空区间。

    Raises:
        ValueError: 输入缺少必需列。
    """
    missing = [col for col in _REQUIRED_COLUMNS if col not in df.columns]
    if missing:
        raise ValueError(f"重采样输入缺少必需列: {missing}")

    indexed = df.copy()
    indexed["date"] = pd.to_datetime(indexed["date"])
    indexed = indexed.sort_values("date").set_index("date")

    rules = {col: agg for col, agg in AGGREGATION_RULES.items() if col in indexed.columns}
    resampled = indexed.resample(rule).agg(rules).dropna(subset=["open", "close"]).reset_index()

    logger.info("重采样 %s: %d 条 -> %d 条", rule, len(df), len(resampled))
    return resampled


def align_frames(frames: Dict[str, pd.DataFrame], column: str = "close") -> pd.DataFrame:
    """把多个品种的行情按日期对齐成一张宽表。

    Args:
        frames: ``{品种代码: OHLCV DataFrame}``。
        column: 取用的列名，默认收盘价。

    Returns:
        以 date 为索引、各品种为列的 DataFrame，仅保留全部品种都有数据的日期。
    """
    series = {
        symbol: df.set_index(pd.to_datetime(df["date"]))[column] for symbol, df in frames.items()
    }
    aligned = pd.DataFrame(series).dropna()
    aligned.index.name = "date"
    return aligned
