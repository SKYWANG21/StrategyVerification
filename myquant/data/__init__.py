"""数据层入口：数据源注册表与工厂。

新增数据源只需实现 :class:`~myquant.data.base_datafeed.BaseDataFeed` 并调用
:func:`register_feed` 注册，上层通过 :func:`get_feed` 获取实例，无需改动引擎与策略。
"""

from __future__ import annotations

import logging
from typing import Dict, List, Optional, Type

from myquant.config import get_data_source_config, get_default_source
from myquant.data.base_datafeed import OHLCV_COLUMNS, BaseDataFeed, Market

logger = logging.getLogger(__name__)

_FEED_REGISTRY: Dict[str, Type[BaseDataFeed]] = {}


def register_feed(name: str, feed_cls: Type[BaseDataFeed]) -> None:
    """注册数据源实现。

    Args:
        name: 数据源名称，需与 ``data_sources.yaml`` 中的键一致。
        feed_cls: :class:`BaseDataFeed` 的子类。
    """
    _FEED_REGISTRY[name] = feed_cls


def available_sources() -> List[str]:
    """返回已注册的数据源名称列表。"""
    return sorted(_FEED_REGISTRY)


def get_feed(source: Optional[str] = None) -> BaseDataFeed:
    """按名称创建数据源实例。

    Args:
        source: 数据源名称；为 None 时使用 ``data_sources.yaml`` 中的默认源。

    Returns:
        数据源实例。

    Raises:
        KeyError: 数据源未注册。
    """
    name = source or get_default_source()
    if name not in _FEED_REGISTRY:
        raise KeyError(f"未注册的数据源: {name}，可选: {available_sources()}")

    config = get_data_source_config(name)
    logger.info("创建数据源: %s", name)
    return _FEED_REGISTRY[name](config)


def _register_builtin_feeds() -> None:
    """注册内置数据源。

    akshare / tushare 的第三方库在实例化时才导入，这里只注册类，
    避免未安装某个库就无法使用另一个数据源。
    """
    from myquant.data.akshare_feed import AkshareFeed
    from myquant.data.tushare_feed import TushareFeed

    register_feed("akshare", AkshareFeed)
    register_feed("tushare", TushareFeed)


_register_builtin_feeds()

__all__ = [
    "OHLCV_COLUMNS",
    "BaseDataFeed",
    "Market",
    "available_sources",
    "get_feed",
    "register_feed",
]
