"""虚拟券商（骨架）。

后续阶段将实现：按最新价撮合、T+0/T+1 规则、佣金与滑点模拟、逐日盯市。
"""

from __future__ import annotations

from typing import Dict, Optional

from myquant.live.base_broker import BaseBroker, Order, Position


class VirtualBroker(BaseBroker):
    """基于实时行情的虚拟撮合经纪商。

    Attributes:
        cash: 可用现金。
        positions: 品种代码到持仓的映射。
    """

    def __init__(self, initial_cash: float = 1_000_000.0) -> None:
        """初始化虚拟账户。

        Args:
            initial_cash: 初始虚拟资金。
        """
        self.cash = initial_cash
        self.positions: Dict[str, Position] = {}

    def submit_order(self, order: Order) -> str:
        """提交订单（待实现）。

        Args:
            order: 订单请求。

        Returns:
            订单编号。

        Raises:
            NotImplementedError: 撮合逻辑尚未实现。
        """
        # TODO(第二阶段): 按最新价撮合，扣减现金与手续费，更新持仓
        raise NotImplementedError("虚拟撮合尚未实现")

    def get_position(self, symbol: str) -> Optional[Position]:
        """查询持仓。

        Args:
            symbol: 品种代码。

        Returns:
            持仓快照；无持仓时返回 None。
        """
        return self.positions.get(symbol)

    def get_cash(self) -> float:
        """返回可用现金。"""
        return self.cash

    def get_value(self) -> float:
        """返回账户总权益（待实现盯市估值）。

        Raises:
            NotImplementedError: 需要接入实时价格后才能估值。
        """
        # TODO(第二阶段): 用最新行情对持仓做盯市估值
        raise NotImplementedError("账户盯市估值尚未实现")
