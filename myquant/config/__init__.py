"""配置加载模块。

职责：读取 ``settings.yaml`` 与 ``data_sources.yaml``，展开 ``${ENV_VAR}`` 占位符，
并向上层提供路径、市场参数、品种参数与日志初始化能力。

其他模块统一通过本模块读取配置，禁止在业务代码中硬编码参数。
"""

from __future__ import annotations

import logging
import os
import re
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Optional

import yaml

CONFIG_DIR: Path = Path(__file__).resolve().parent
PACKAGE_ROOT: Path = CONFIG_DIR.parent
SETTINGS_FILE: Path = CONFIG_DIR / "settings.yaml"
DATA_SOURCES_FILE: Path = CONFIG_DIR / "data_sources.yaml"

_ENV_PATTERN = re.compile(r"\$\{([^}]+)\}")

logger = logging.getLogger(__name__)


def _expand_env(value: Any) -> Any:
    """递归展开配置中的 ``${ENV_VAR}`` 占位符。

    Args:
        value: 任意配置节点（dict / list / str / 标量）。

    Returns:
        展开后的同结构对象；未设置的环境变量替换为空字符串。
    """
    if isinstance(value, dict):
        return {key: _expand_env(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_expand_env(item) for item in value]
    if isinstance(value, str):
        return _ENV_PATTERN.sub(lambda m: os.getenv(m.group(1), ""), value)
    return value


def _load_yaml(path: Path) -> Dict[str, Any]:
    """读取 YAML 文件并展开环境变量。

    Args:
        path: YAML 文件路径。

    Returns:
        配置字典；文件为空时返回空字典。

    Raises:
        FileNotFoundError: 配置文件不存在。
    """
    if not path.exists():
        raise FileNotFoundError(f"配置文件不存在: {path}")
    with path.open("r", encoding="utf-8") as fp:
        raw = yaml.safe_load(fp) or {}
    return _expand_env(raw)


@lru_cache(maxsize=1)
def load_settings() -> Dict[str, Any]:
    """加载并缓存 ``settings.yaml``。

    Returns:
        全局参数字典。
    """
    return _load_yaml(SETTINGS_FILE)


@lru_cache(maxsize=1)
def load_data_sources() -> Dict[str, Any]:
    """加载并缓存 ``data_sources.yaml``。

    Returns:
        数据源配置字典。
    """
    return _load_yaml(DATA_SOURCES_FILE)


def get_settings(section: Optional[str] = None) -> Dict[str, Any]:
    """读取全局参数。

    Args:
        section: 配置段名（如 ``backtest``、``logging``）；为 None 时返回全部。

    Returns:
        对应配置段字典；段不存在时返回空字典。
    """
    settings = load_settings()
    if section is None:
        return settings
    return settings.get(section, {})


def get_data_source_config(name: Optional[str] = None) -> Dict[str, Any]:
    """读取单个数据源配置。

    Args:
        name: 数据源名（``akshare`` / ``tushare``）；为 None 时用配置中的默认源。

    Returns:
        含 ``name`` 字段的数据源配置字典。

    Raises:
        KeyError: 数据源未在 ``data_sources.yaml`` 中定义。
    """
    config = load_data_sources()
    source_name = name or config.get("default", "akshare")
    sources = config.get("sources", {})
    if source_name not in sources:
        raise KeyError(f"未定义的数据源: {source_name}，可选: {list(sources)}")
    return {"name": source_name, **sources[source_name]}


def get_default_source() -> str:
    """返回默认数据源名称。"""
    return load_data_sources().get("default", "akshare")


def get_market_config(market: str) -> Dict[str, Any]:
    """读取某市场的默认交易参数。

    Args:
        market: 市场标识（``cn_stock`` / ``us_stock`` / ``crypto`` / ``futures``）。

    Returns:
        含手续费、滑点、保证金比例、合约乘数的字典。

    Raises:
        KeyError: 市场未在 ``settings.yaml`` 的 ``markets`` 段中定义。
    """
    markets = get_settings("markets")
    if market not in markets:
        raise KeyError(f"未定义的市场: {market}，可选: {list(markets)}")
    return dict(markets[market])


def get_instrument_config(symbol: str, market: Optional[str] = None) -> Dict[str, Any]:
    """读取品种交易参数：市场默认值叠加品种级覆盖。

    Args:
        symbol: 品种代码（如 ``RB0``、``000001``、``AAPL``）。
        market: 市场标识；为 None 时优先取品种配置里声明的 market，再回退 ``cn_stock``。

    Returns:
        合并后的品种参数字典，至少包含 commission、slippage、margin_rate、
        contract_multiplier、market 字段。
    """
    instruments = get_settings("instruments")
    instrument = dict(instruments.get(symbol, {}))
    resolved_market = market or instrument.get("market") or "cn_stock"

    config = get_market_config(resolved_market)
    config.update(instrument)
    config["market"] = resolved_market
    config.setdefault("name", symbol)
    return config


def get_paths() -> Dict[str, Path]:
    """返回结果、日志、缓存等目录的绝对路径。

    Returns:
        路径字典，键为 ``package_root`` 及 ``settings.yaml`` 中 ``paths`` 段的键。
    """
    paths: Dict[str, Path] = {"package_root": PACKAGE_ROOT}
    for key, value in get_settings("paths").items():
        paths[key] = PACKAGE_ROOT / value
    return paths


def ensure_directories() -> None:
    """创建配置中声明的全部目录（已存在则跳过）。"""
    for key, path in get_paths().items():
        if key == "package_root":
            continue
        path.mkdir(parents=True, exist_ok=True)


def setup_logging() -> None:
    """按配置初始化根 logger，同时输出到控制台与日志文件。"""
    log_config = get_settings("logging")
    ensure_directories()
    log_file = get_paths()["logs"] / log_config.get("file", "strategy.log")

    logging.basicConfig(
        level=getattr(logging, str(log_config.get("level", "INFO")).upper(), logging.INFO),
        format=log_config.get("format", "%(asctime)s - %(name)s - %(levelname)s - %(message)s"),
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(log_file, encoding="utf-8"),
        ],
    )


__all__ = [
    "PACKAGE_ROOT",
    "ensure_directories",
    "get_data_source_config",
    "get_default_source",
    "get_instrument_config",
    "get_market_config",
    "get_paths",
    "get_settings",
    "load_data_sources",
    "load_settings",
    "setup_logging",
]
