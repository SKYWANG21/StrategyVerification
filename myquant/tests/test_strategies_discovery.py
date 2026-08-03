"""策略自动发现机制的单元测试。"""

from __future__ import annotations

import pytest

from myquant.strategies import BaseStrategy, discover_strategies, get_strategy, list_strategies


def test_discover_includes_builtin_strategies() -> None:
    """内置的两个策略应能被自动发现。"""
    strategies = discover_strategies()

    assert {"ma20_trend", "ma_cross"} <= set(strategies)
    assert all(issubclass(cls, BaseStrategy) for cls in strategies.values())


def test_get_strategy_returns_class() -> None:
    """按名称可取到策略类。"""
    assert get_strategy("ma20_trend").strategy_name == "MA20趋势跟踪"


def test_get_strategy_unknown_name() -> None:
    """不存在的策略名应报错并提示可选项。"""
    with pytest.raises(KeyError, match="未找到策略"):
        get_strategy("not_exist")


def test_list_strategies_sorted() -> None:
    """策略列表按名称排序返回。"""
    names = list_strategies()

    assert names == sorted(names)
