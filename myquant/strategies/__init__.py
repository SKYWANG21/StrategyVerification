"""策略库入口：自动发现可插拔策略。

约定：每个策略占一个子文件夹，其 ``__init__.py`` 通过 ``STRATEGY`` 变量导出
继承自 :class:`~myquant.strategies.base_strategy.BaseStrategy` 的策略类。
新增策略无需注册，放进目录即可被发现。
"""

from __future__ import annotations

import importlib
import logging
import pkgutil
from pathlib import Path
from typing import Dict, List, Type

from myquant.strategies.base_strategy import BaseStrategy

logger = logging.getLogger(__name__)

PACKAGE_DIR: Path = Path(__file__).resolve().parent


def discover_strategies() -> Dict[str, Type[BaseStrategy]]:
    """扫描策略目录，返回全部可用策略。

    Returns:
        ``{策略目录名: 策略类}``；导入失败或未导出 ``STRATEGY`` 的目录会被跳过并记警告。
    """
    strategies: Dict[str, Type[BaseStrategy]] = {}

    for module_info in pkgutil.iter_modules([str(PACKAGE_DIR)]):
        if not module_info.ispkg:
            continue

        name = module_info.name
        try:
            module = importlib.import_module(f"{__name__}.{name}")
        except Exception as exc:  # 单个策略导入失败不应影响其余策略
            logger.warning("策略 %s 导入失败: %s", name, exc)
            continue

        strategy_cls = getattr(module, "STRATEGY", None)
        if strategy_cls is None or not issubclass(strategy_cls, BaseStrategy):
            logger.warning("策略 %s 未导出合法的 STRATEGY，已跳过", name)
            continue

        strategies[name] = strategy_cls

    return strategies


def get_strategy(name: str) -> Type[BaseStrategy]:
    """按名称获取策略类。

    Args:
        name: 策略目录名，如 ``ma20_trend``。

    Returns:
        策略类。

    Raises:
        KeyError: 策略不存在。
    """
    strategies = discover_strategies()
    if name not in strategies:
        raise KeyError(f"未找到策略: {name}，可选: {sorted(strategies)}")
    return strategies[name]


def list_strategies() -> List[str]:
    """返回全部策略名称列表。"""
    return sorted(discover_strategies())


__all__ = ["BaseStrategy", "discover_strategies", "get_strategy", "list_strategies"]
