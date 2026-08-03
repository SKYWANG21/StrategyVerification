"""数据清洗模块单元测试。"""

from __future__ import annotations

import pandas as pd
import pytest

from myquant.data.cleaner import (
    align_frames,
    fill_missing,
    filter_date_range,
    normalize_ohlcv,
    resample_bars,
    validate_ohlcv,
)


def test_normalize_ohlcv_renames_and_sorts() -> None:
    """列名映射、类型转换、排序与补齐 open_interest 应同时生效。"""
    raw = pd.DataFrame(
        {
            "日期": ["2024-01-03", "2024-01-02"],
            "开盘": ["10.0", "9.5"],
            "最高": ["10.5", "9.8"],
            "最低": ["9.8", "9.2"],
            "收盘": ["10.2", "9.6"],
            "成交量": ["100", "200"],
        }
    )
    rename_map = {
        "日期": "date",
        "开盘": "open",
        "最高": "high",
        "最低": "low",
        "收盘": "close",
        "成交量": "volume",
    }

    result = normalize_ohlcv(raw, rename_map)

    assert list(result["date"].dt.strftime("%Y-%m-%d")) == ["2024-01-02", "2024-01-03"]
    assert result["close"].dtype.kind == "f"
    assert (result["open_interest"] == 0).all()


def test_normalize_ohlcv_missing_column() -> None:
    """缺少必需列时应抛出明确错误。"""
    with pytest.raises(ValueError, match="缺少必需列"):
        normalize_ohlcv(pd.DataFrame({"date": ["2024-01-01"], "close": [1.0]}))


def test_validate_ohlcv_detects_invalid_high(daily_ohlcv: pd.DataFrame) -> None:
    """high 低于 close 时应被识别为问题。"""
    assert validate_ohlcv(daily_ohlcv) == []

    broken = daily_ohlcv.copy()
    broken.loc[0, "high"] = broken.loc[0, "close"] - 1
    assert any("high" in issue for issue in validate_ohlcv(broken))


def test_fill_missing_forward_fills(daily_ohlcv: pd.DataFrame) -> None:
    """前向填充后价格列不应再有缺失值。"""
    holed = daily_ohlcv.copy()
    holed.loc[5, "close"] = None

    filled = fill_missing(holed, method="ffill")

    assert filled["close"].isna().sum() == 0
    assert filled.loc[5, "close"] == holed.loc[4, "close"]


def test_filter_date_range(daily_ohlcv: pd.DataFrame) -> None:
    """日期过滤应包含端点。"""
    filtered = filter_date_range(daily_ohlcv, "2023-02-01", "2023-02-28")

    assert filtered["date"].min() >= pd.Timestamp("2023-02-01")
    assert filtered["date"].max() <= pd.Timestamp("2023-02-28")


def test_resample_bars_halves_rows(daily_ohlcv: pd.DataFrame) -> None:
    """2 日 K 线条数约为日线的一半，且 OHLC 聚合正确。"""
    resampled = resample_bars(daily_ohlcv, "2D")

    assert 0.4 <= len(resampled) / len(daily_ohlcv) <= 0.7
    assert (resampled["high"] >= resampled[["open", "close"]].max(axis=1)).all()
    assert (resampled["low"] <= resampled[["open", "close"]].min(axis=1)).all()


def test_align_frames(daily_ohlcv: pd.DataFrame) -> None:
    """多品种对齐后只保留共同日期。"""
    other = daily_ohlcv.iloc[10:].copy()

    aligned = align_frames({"A": daily_ohlcv, "B": other})

    assert list(aligned.columns) == ["A", "B"]
    assert len(aligned) == len(other)
