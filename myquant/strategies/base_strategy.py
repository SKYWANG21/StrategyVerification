"""策略基类。

封装所有策略共用的能力：订单/成交日志、交易记录收集、基于风险与保证金的仓位计算。
具体策略只需实现 :meth:`next` 中的进出场逻辑。
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

import backtrader as bt

logger = logging.getLogger(__name__)


class BaseStrategy(bt.Strategy):
    """所有策略的基类。

    Attributes:
        strategy_name: 策略展示名，用于报告与结果目录命名。
        trade_records: 已平仓交易记录，供绩效分析与导出使用。
    """

    strategy_name: str = "base"

    params = (
        ("printlog", False),  # 是否打印逐笔日志
        ("risk_per_trade", 0.02),  # 单笔风险占总资金比例
        ("max_position_pct", 0.8),  # 最大仓位占资金比例
        ("min_position_size", 1),  # 最小下单数量
        ("margin_rate", 1.0),  # 保证金比例，股票/现货为 1.0
        ("contract_multiplier", 1),  # 合约乘数，股票/现货为 1
    )

    def __init__(self) -> None:
        """初始化订单状态与交易记录容器。"""
        self.order: Optional[bt.Order] = None
        self.trade_records: List[Dict[str, Any]] = []

    def log(self, txt: str, dt: Optional[Any] = None) -> None:
        """打印带日期前缀的策略日志。

        Args:
            txt: 日志内容。
            dt: 日志时间，缺省取当前 K 线日期。
        """
        if not self.p.printlog:
            return
        stamp = dt or self.data.datetime.date(0)
        logger.info("%s %s", stamp, txt)

    def notify_order(self, order: bt.Order) -> None:
        """订单状态回调：成交时记日志，终态时释放订单占用。

        Args:
            order: Backtrader 订单对象。
        """
        if order.status in (order.Submitted, order.Accepted):
            return

        if order.status == order.Completed:
            action = "买入" if order.isbuy() else "卖出"
            self.log(
                f"{action}成交 价={order.executed.price:.2f} "
                f"量={order.executed.size} 手续费={order.executed.comm:.2f}"
            )
        elif order.status in (order.Canceled, order.Margin, order.Rejected):
            self.log(f"订单未成交，状态: {order.getstatusname()}")

        self.order = None

    def notify_trade(self, trade: bt.Trade) -> None:
        """成交回调：平仓时登记一条交易记录。

        Args:
            trade: Backtrader 交易对象。
        """
        if not trade.isclosed:
            return

        self.trade_records.append(
            {
                "date": self.data.datetime.date(0),
                "price": trade.price,
                "size": trade.size,
                "pnl": trade.pnl,
                "pnl_comm": trade.pnlcomm,
                "bars_held": trade.barlen,
            }
        )
        self.log(f"平仓 盈亏={trade.pnl:.2f} 净盈亏={trade.pnlcomm:.2f}")

    def size_by_risk(self, entry_price: float, stop_price: float) -> int:
        """按单笔风险与保证金上限计算下单数量。

        取“风险限制手数”与“保证金限制手数”的较小值，且不低于最小下单数量。

        Args:
            entry_price: 进场价格。
            stop_price: 止损价格。

        Returns:
            建议下单数量；进场价与止损价相同等无效情况返回 0。
        """
        multiplier = float(self.p.contract_multiplier)
        risk_per_unit = abs(entry_price - stop_price) * multiplier
        margin_per_unit = entry_price * multiplier * float(self.p.margin_rate)

        if risk_per_unit <= 0 or margin_per_unit <= 0:
            return 0

        capital = self.broker.getvalue()
        max_by_risk = int(capital * float(self.p.risk_per_trade) / risk_per_unit)
        max_by_margin = int(capital * float(self.p.max_position_pct) / margin_per_unit)
        size = min(max_by_risk, max_by_margin)

        if size < int(self.p.min_position_size):
            # 资金不足以按最小单位开仓时放弃本次信号
            return int(self.p.min_position_size) if max_by_margin >= 1 else 0
        return size

    def get_trades(self) -> List[Dict[str, Any]]:
        """返回已平仓交易记录列表。"""
        return self.trade_records

    def stop(self) -> None:
        """回测结束时输出最终净值。"""
        self.log(f"策略结束，最终净值: {self.broker.getvalue():.2f}")
