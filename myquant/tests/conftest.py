"""pytest 公共夹具。"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

# 允许在仓库任意目录下执行 pytest
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))


@pytest.fixture
def daily_ohlcv() -> pd.DataFrame:
    """生成一段带上升趋势的模拟日线数据。

    Returns:
        含标准 OHLCV 列的 DataFrame，共 300 个交易日。
    """
    rng = np.random.default_rng(42)
    dates = pd.bdate_range(start="2023-01-02", periods=300)
    close = 4000 + np.cumsum(rng.normal(loc=1.5, scale=30, size=len(dates)))

    frame = pd.DataFrame(
        {
            "date": dates,
            "open": close + rng.normal(0, 10, len(dates)),
            "high": close + rng.uniform(5, 40, len(dates)),
            "low": close - rng.uniform(5, 40, len(dates)),
            "close": close,
            "volume": rng.integers(10_000, 100_000, len(dates)),
        }
    )
    frame["high"] = frame[["high", "open", "close"]].max(axis=1)
    frame["low"] = frame[["low", "open", "close"]].min(axis=1)
    return frame
