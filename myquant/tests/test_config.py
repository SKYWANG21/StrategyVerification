"""配置加载模块的单元测试。"""

from __future__ import annotations

import pytest

from myquant.config import (
    get_data_source_config,
    get_instrument_config,
    get_market_config,
    get_paths,
    get_settings,
)


def test_settings_sections_exist() -> None:
    """核心配置段应齐备。"""
    settings = get_settings()

    assert {"paths", "logging", "backtest", "markets", "instruments"} <= set(settings)
    assert get_settings("backtest")["initial_capital"] > 0


def test_instrument_inherits_market_defaults() -> None:
    """未单独配置的品种应继承所属市场的默认参数。"""
    stock = get_instrument_config("000001", "cn_stock")

    assert stock["market"] == "cn_stock"
    assert stock["margin_rate"] == 1.0
    assert stock["contract_multiplier"] == 1


def test_instrument_overrides_market_defaults() -> None:
    """品种级参数应覆盖市场默认值。"""
    futures = get_instrument_config("RB0")

    assert futures["market"] == "futures"
    assert futures["contract_multiplier"] == 10
    assert futures["margin_rate"] == 0.10


def test_unknown_market_raises() -> None:
    """未定义的市场应报错。"""
    with pytest.raises(KeyError):
        get_market_config("forex")


def test_data_source_config_has_name() -> None:
    """数据源配置需带上自身名称，便于工厂使用。"""
    config = get_data_source_config("akshare")

    assert config["name"] == "akshare"
    assert "interfaces" in config


def test_paths_are_absolute() -> None:
    """路径配置应展开为绝对路径。"""
    paths = get_paths()

    assert paths["results"].is_absolute()
    assert paths["results"].name == "results"
