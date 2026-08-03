"""模拟交易经纪商抽象接口。

第一阶段只定义接口，撮合与资金管理在后续阶段实现。接口独立于回测引擎，
未来可替换为 vnpy、Alpaca Paper Trading 等外部模拟环境。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional


class OrderSide(str, Enum):
    """订单方向。"""

    BUY = "buy"
    SELL = "sell"


@dataclass
class Order:
    """订单请求。

    Attributes:
        symbol: 品种代码。
        side: 买卖方向。
        size: 下单数量。
        price: 委托价；为 None 表示市价单。
        created_at: 委托时间。
    """

    symbol: str
    side: OrderSide
    size: int
    price: Optional[float] = None
    created_at: datetime = datetime.now()


@dataclass
class Position:
    """持仓快照。

    Attributes:
        symbol: 品种代码。
        size: 持仓数量，正数为多头、负数为空头。
        avg_price: 持仓均价。
    """

    symbol: str
    size: int
    avg_price: float


class BaseBroker(ABC):
    """模拟经纪商接口。"""

    @abstractmethod
    def submit_order(self, order: Order) -> str:
        """提交订单。

        Args:
            order: 订单请求。

        Returns:
            订单编号。
        """

    @abstractmethod
    def get_position(self, symbol: str) -> Optional[Position]:
        """查询持仓。

        Args:
            symbol: 品种代码。

        Returns:
            持仓快照；无持仓时返回 None。
        """

    @abstractmethod
    def get_cash(self) -> float:
        """返回可用现金。"""

    @abstractmethod
    def get_value(self) -> float:
        """返回账户总权益。"""
