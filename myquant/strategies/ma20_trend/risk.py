"""MA20 趋势跟踪策略 - 止损逻辑。

止损规则：
- 基础止损取前一根 K 线极值（做多用前低、做空用前高）
- 若基础止损距离超过 ``max_loss_pct``，改用 ``force_stop_pct`` 的强制止损
- 有浮盈后把止损上移/下移到成本价（保本）

仓位计算在 :class:`~myquant.strategies.base_strategy.BaseStrategy` 中统一处理。
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class StopLossResult:
    """止损计算结果。

    Attributes:
        stop_price: 止损价格。
        stop_distance_pct: 止损距离占进场价的比例。
        is_forced: 是否触发了强制止损。
        reason: 计算依据说明。
    """

    stop_price: float
    stop_distance_pct: float
    is_forced: bool
    reason: str


def calculate_stop_loss(
    entry_price: float,
    prev_extreme: float,
    is_long: bool,
    max_loss_pct: float = 0.06,
    force_stop_pct: float = 0.03,
) -> StopLossResult:
    """计算开仓止损价。

    Args:
        entry_price: 进场价格。
        prev_extreme: 前一根 K 线极值，做多传前低、做空传前高。
        is_long: 是否为多头方向。
        max_loss_pct: 基础止损可接受的最大距离比例。
        force_stop_pct: 超出容忍度时使用的强制止损比例。

    Returns:
        止损计算结果。

    Raises:
        ValueError: 进场价非正数。
    """
    if entry_price <= 0:
        raise ValueError(f"进场价必须为正数，收到: {entry_price}")

    direction = 1.0 if is_long else -1.0
    base_distance_pct = direction * (entry_price - prev_extreme) / entry_price
    forced_price = entry_price * (1 - direction * force_stop_pct)

    # 基础止损方向反了（前低高于进场价 / 前高低于进场价）同样退回强制止损
    if base_distance_pct <= 0:
        return StopLossResult(
            stop_price=forced_price,
            stop_distance_pct=force_stop_pct,
            is_forced=True,
            reason=f"前极值 {prev_extreme:.2f} 位于进场价错误一侧，改用强制止损",
        )

    if base_distance_pct > max_loss_pct:
        return StopLossResult(
            stop_price=forced_price,
            stop_distance_pct=force_stop_pct,
            is_forced=True,
            reason=(
                f"基础止损距离 {base_distance_pct:.2%} 超过容忍度 {max_loss_pct:.2%}，"
                f"改用 {force_stop_pct:.2%} 强制止损"
            ),
        )

    return StopLossResult(
        stop_price=prev_extreme,
        stop_distance_pct=base_distance_pct,
        is_forced=False,
        reason=f"基础止损距离 {base_distance_pct:.2%} 在容忍范围内",
    )


def is_stop_triggered(low: float, high: float, stop_price: float, is_long: bool) -> bool:
    """判断当前 K 线是否触及止损。

    Args:
        low: 当根 K 线最低价。
        high: 当根 K 线最高价。
        stop_price: 止损价格。
        is_long: 是否为多头持仓。

    Returns:
        触及止损返回 True。
    """
    return low <= stop_price if is_long else high >= stop_price


def breakeven_stop(entry_price: float, current_price: float, is_long: bool) -> float | None:
    """浮盈时把止损移到成本价。

    Args:
        entry_price: 进场价格。
        current_price: 当前价格。
        is_long: 是否为多头持仓。

    Returns:
        应移动到的止损价（即成本价）；尚无浮盈时返回 None。
    """
    has_profit = current_price > entry_price if is_long else current_price < entry_price
    return entry_price if has_profit else None


def trailing_stop(extreme_price: float, is_long: bool, trailing_pct: float = 0.02) -> float:
    """按持仓期极值计算跟踪止损价。

    Args:
        extreme_price: 持仓期间的极值价，做多取最高价、做空取最低价。
        is_long: 是否为多头持仓。
        trailing_pct: 允许的回撤比例。

    Returns:
        跟踪止损价格。
    """
    direction = 1.0 if is_long else -1.0
    return extreme_price * (1 - direction * trailing_pct)
