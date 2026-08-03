"""MA20 趋势跟踪策略的信号与止损单元测试。"""

from __future__ import annotations

import pandas as pd
import pytest

from myquant.strategies.ma20_trend.risk import (
    breakeven_stop,
    calculate_stop_loss,
    is_stop_triggered,
    trailing_stop,
)
from myquant.strategies.ma20_trend.signals import Signal, generate_signals, signal_at


def test_signal_at_long_and_short() -> None:
    """价在均线上方且收阳做多，下方且收阴做空，其余观望。"""
    assert signal_at(close=110, open_=105, ma=100) is Signal.BUY
    assert signal_at(close=90, open_=95, ma=100) is Signal.SELL
    assert signal_at(close=110, open_=115, ma=100) is Signal.WAIT
    assert signal_at(close=110, open_=105, ma=None) is Signal.WAIT
    assert signal_at(close=110, open_=105, ma=float("nan")) is Signal.WAIT


def test_generate_signals_adds_columns(daily_ohlcv: pd.DataFrame) -> None:
    """批量信号计算应补齐均线、K 线特征与 signal 列。"""
    result = generate_signals(daily_ohlcv, ma_period=20)

    assert {"ma20", "is_red", "body_ratio", "signal"} <= set(result.columns)
    assert set(result["signal"].unique()) <= {-1, 0, 1}
    assert result["ma20"].isna().sum() == 19


def test_calculate_stop_loss_uses_prev_extreme() -> None:
    """止损距离在容忍范围内时直接使用前一根 K 线极值。"""
    result = calculate_stop_loss(entry_price=100, prev_extreme=97, is_long=True)

    assert result.stop_price == 97
    assert result.is_forced is False
    assert result.stop_distance_pct == pytest.approx(0.03)


def test_calculate_stop_loss_falls_back_to_forced() -> None:
    """超出容忍度时改用强制止损比例。"""
    long_result = calculate_stop_loss(entry_price=100, prev_extreme=80, is_long=True)
    short_result = calculate_stop_loss(entry_price=100, prev_extreme=120, is_long=False)

    assert long_result.is_forced is True
    assert long_result.stop_price == pytest.approx(97.0)
    assert short_result.is_forced is True
    assert short_result.stop_price == pytest.approx(103.0)


def test_calculate_stop_loss_wrong_side_extreme() -> None:
    """前极值落在进场价错误一侧时同样退回强制止损。"""
    result = calculate_stop_loss(entry_price=100, prev_extreme=105, is_long=True)

    assert result.is_forced is True
    assert result.stop_price == pytest.approx(97.0)


def test_calculate_stop_loss_rejects_invalid_entry() -> None:
    """进场价非正数应报错。"""
    with pytest.raises(ValueError):
        calculate_stop_loss(entry_price=0, prev_extreme=1, is_long=True)


def test_is_stop_triggered() -> None:
    """多头看最低价、空头看最高价是否触及止损。"""
    assert is_stop_triggered(low=96, high=101, stop_price=97, is_long=True) is True
    assert is_stop_triggered(low=98, high=101, stop_price=97, is_long=True) is False
    assert is_stop_triggered(low=98, high=104, stop_price=103, is_long=False) is True


def test_breakeven_and_trailing_stop() -> None:
    """浮盈后止损移到成本价；跟踪止损按极值回撤计算。"""
    assert breakeven_stop(entry_price=100, current_price=105, is_long=True) == 100
    assert breakeven_stop(entry_price=100, current_price=98, is_long=True) is None
    assert trailing_stop(extreme_price=110, is_long=True, trailing_pct=0.02) == pytest.approx(107.8)
    assert trailing_stop(extreme_price=90, is_long=False, trailing_pct=0.02) == pytest.approx(91.8)
