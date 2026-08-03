"""
MA20趋势跟踪策略 - Backtrader 回测引擎

【面向初学者】
本模块使用 Backtrader 框架做“逐 K 线”回测：
- MA20Strategy：在 next() 里根据当前 close、open、MA20 判断开多/开空，并用 RiskManager 算止损与手数；
  有持仓时检查移动止损（浮盈提到保本）和 K 线反转平仓。
- BacktestEngine：准备 PandasData、设置 Cerebro（资金、手续费、滑点）、运行策略并汇总 returns/sharpe/drawdown/trades 等结果。

若不想依赖 Backtrader，可使用 scripts/main_simple.py 中的简化回测逻辑。
"""

import backtrader as bt
import pandas as pd
import logging
from typing import Dict, Any

from config import get_config, get_instrument_config
from src.signal_generator import SignalGenerator
from src.risk_manager import RiskManager, PositionSide

logger = logging.getLogger(__name__)


class MA20Strategy(bt.Strategy):
    """
    Backtrader 策略类：每个 next() 调用对应一根 2 日 K 线。
    无仓时根据 收盘>MA20 且 收阳 开多，收盘<MA20 且 收阴 开空；
    有仓时浮盈则移动止损到成本价，K 线颜色反转则平仓。
    """
    params = (
        ('ma_period', 20),
        ('max_loss_pct', 0.06),
        ('force_stop_pct', 0.03),
        ('risk_per_trade', 0.02),
        ('symbol', 'RB0'),
        ('commission', 0.0003),
        ('margin_rate', 0.10),
        ('contract_multiplier', 10),
        ('slippage', 0.001),
        ('printlog', True),
    )

    def __init__(self):
        self.ma20 = bt.indicators.SimpleMovingAverage(self.data.close, period=self.p.ma_period)
        self.signal_generator = SignalGenerator(ma_period=self.p.ma_period)
        self.risk_manager = RiskManager()

        self.order = None
        self.entry_price = None
        self.stop_price = None
        self.position_size = None
        self.position_side = PositionSide.NONE
        self.prev_extreme = None   # 前一根 K 的 high/low，用于算止损
        self.extreme_price = None
        self.trades = []
        self.signals = []
        self.stop_moved_to_breakeven = False  # 是否已把止损移到成本价
        logger.info(f"MA20策略初始化完成，周期: {self.p.ma_period}")

    def next(self):
        if len(self.data) > 1:
            self.prev_extreme = {'high': self.data.high[-1], 'low': self.data.low[-1]}
        if self.order:
            return
        if self.position:
            self._check_exit_conditions()
        else:
            self._check_entry_conditions()

    def _check_entry_conditions(self):
        current_price = self.data.close[0]
        current_open = self.data.open[0]
        ma_value = self.ma20[0]
        if len(self.data) < self.p.ma_period + 1:
            return
        if current_price > ma_value and current_price > current_open:
            if self.prev_extreme:
                self._enter_long_position()
        elif current_price < ma_value and current_price < current_open:
            if self.prev_extreme:
                self._enter_short_position()

    def _enter_long_position(self):
        stop_result = self.risk_manager.calculate_stop_loss(
            entry_price=self.data.close[0],
            prev_extreme=self.prev_extreme['low'],
            direction=PositionSide.LONG
        )
        capital = self.broker.getvalue()
        position_result = self.risk_manager.calculate_position_size(
            capital=capital,
            entry_price=self.data.close[0],
            stop_price=stop_result.stop_price,
            margin_rate=self.p.margin_rate,
            contract_multiplier=self.p.contract_multiplier
        )
        size = int(position_result.position_size)
        if size <= 0:
            return
        self.entry_price = self.data.close[0]
        self.stop_price = stop_result.stop_price
        self.position_size = size
        self.position_side = PositionSide.LONG
        self.order = self.buy(size=size)
        self.stop_moved_to_breakeven = False
        logger.info(f"开多: 价{self.entry_price:.2f} 手{size} 止损{self.stop_price:.2f}")

    def _enter_short_position(self):
        stop_result = self.risk_manager.calculate_stop_loss(
            entry_price=self.data.close[0],
            prev_extreme=self.prev_extreme['high'],
            direction=PositionSide.SHORT
        )
        capital = self.broker.getvalue()
        position_result = self.risk_manager.calculate_position_size(
            capital=capital,
            entry_price=self.data.close[0],
            stop_price=stop_result.stop_price,
            margin_rate=self.p.margin_rate,
            contract_multiplier=self.p.contract_multiplier
        )
        size = int(position_result.position_size)
        if size <= 0:
            return
        self.entry_price = self.data.close[0]
        self.stop_price = stop_result.stop_price
        self.position_size = size
        self.position_side = PositionSide.SHORT
        self.order = self.sell(size=size)
        self.stop_moved_to_breakeven = False
        logger.info(f"开空: 价{self.entry_price:.2f} 手{size} 止损{self.stop_price:.2f}")

    def _check_exit_conditions(self):
        current_price = self.data.close[0]
        current_open = self.data.open[0]
        ma_value = self.ma20[0]

        if self.position_side == PositionSide.LONG:
            if current_price > self.entry_price and not self.stop_moved_to_breakeven:
                self.stop_price = self.entry_price
                self.stop_moved_to_breakeven = True
            if current_price < ma_value and current_price < current_open:
                self.close()
                logger.info("多单止盈/反转平仓")
        elif self.position_side == PositionSide.SHORT:
            if current_price < self.entry_price and not self.stop_moved_to_breakeven:
                self.stop_price = self.entry_price
                self.stop_moved_to_breakeven = True
            if current_price > ma_value and current_price > current_open:
                self.close()
                logger.info("空单止盈/反转平仓")

    def notify_order(self, order):
        if order.status in [order.Completed, order.Canceled, order.Margin]:
            self.order = None

    def notify_trade(self, trade):
        if trade.isclosed:
            pnl = trade.pnl
            date = self.data.datetime.date(0)
            self.trades.append({
                'date': pd.to_datetime(date),
                'type': 'BUY' if pnl >= 0 else 'SELL',
                'price': self.data.close[0],
                'pnl': pnl
            })

    def log(self, txt, dt=None):
        dt = dt or self.data.datetime.datetime(0)
        if self.p.printlog:
            logger.info(f'{dt.isoformat()} {txt}')

    def stop(self):
        self.log(f"策略结束，最终资产: {self.broker.getvalue():.2f}")


class BacktestEngine:
    """
    回测引擎：根据品种从 config 读取手续费、保证金等，将 DataFrame 转为 Backtrader 数据源，
    注册 MA20Strategy 与各类 Analyzer，执行 run 并整理成字典结果，支持打印报告。
    """
    def __init__(self, symbol: str = 'RB0'):
        self.symbol = symbol
        self.config = get_config()
        self.instrument_config = get_instrument_config(symbol)
        self.cerebro = None
        self.results = None
        logger.info(f"回测引擎初始化完成，品种: {symbol}")

    def prepare_data(self, df: pd.DataFrame) -> bt.feeds.PandasData:
        df['date'] = pd.to_datetime(df['date'])
        df = df.set_index('date').sort_index()
        data = bt.feeds.PandasData(
            dataname=df,
            datetime=None,
            open='open', high='high', low='low', close='close',
            volume='volume', openinterest=-1
        )
        return data

    def setup_cerebro(self, df: pd.DataFrame, initial_capital: float = 100000):
        self.cerebro = bt.Cerebro()
        data = self.prepare_data(df)
        self.cerebro.adddata(data)
        self.cerebro.addstrategy(
            MA20Strategy,
            ma_period=self.config['ma_period'],
            max_loss_pct=self.config['max_loss_pct'],
            force_stop_pct=self.config['force_stop_pct'],
            risk_per_trade=self.config['backtest']['risk_per_trade'],
            symbol=self.symbol,
            **self.instrument_config
        )
        self.cerebro.broker.setcash(initial_capital)
        self.cerebro.broker.setcommission(
            commission=self.instrument_config['commission'],
            margin=self.instrument_config['margin_rate'],
            mult=self.instrument_config['contract_multiplier']
        )
        self.cerebro.broker.set_slippage_perc(perc=self.instrument_config['slippage'])
        self._add_analyzers()

    def _add_analyzers(self):
        self.cerebro.addanalyzer(bt.analyzers.Returns, _name='returns')
        self.cerebro.addanalyzer(bt.analyzers.SharpeRatio, _name='sharpe')
        self.cerebro.addanalyzer(bt.analyzers.DrawDown, _name='drawdown')
        self.cerebro.addanalyzer(bt.analyzers.TradeAnalyzer, _name='trades')
        self.cerebro.addanalyzer(bt.analyzers.TimeReturn, _name='timereturn')
        self.cerebro.addanalyzer(bt.analyzers.SQN, _name='sqn')

    def run_backtest(self, df: pd.DataFrame, initial_capital: float = 100000) -> Dict[str, Any]:
        """准备 Cerebro、注入数据与策略、运行并返回汇总结果（资金、收益、回撤、胜率等）。"""
        self.setup_cerebro(df, initial_capital)
        self.results = self.cerebro.run()
        return self._extract_results()

    def _extract_results(self) -> Dict[str, Any]:
        """从 Backtrader 运行结果中提取 basic_info、return_metrics、risk_metrics、trade_metrics、strategy_data。"""
        if not self.results:
            return {}
        strat = self.results[0]
        final_value = self.cerebro.broker.getvalue()
        initial_capital = self.cerebro.broker.startingcash
        total_return = (final_value - initial_capital) / initial_capital
        returns_analyzer = strat.analyzers.returns.get_analysis()
        sharpe_analyzer = strat.analyzers.sharpe.get_analysis()
        drawdown_analyzer = strat.analyzers.drawdown.get_analysis()
        trades_analyzer = strat.analyzers.trades.get_analysis()
        total_trades = trades_analyzer.total.total
        won_trades = trades_analyzer.won.total if hasattr(trades_analyzer.won, 'total') else 0
        lost_trades = trades_analyzer.lost.total if hasattr(trades_analyzer.lost, 'total') else 0
        win_rate = won_trades / total_trades if total_trades > 0 else 0
        pnl_won = trades_analyzer.won.pnl.total if hasattr(trades_analyzer.won, 'pnl') else 0
        pnl_lost = trades_analyzer.lost.pnl.total if hasattr(trades_analyzer.lost, 'pnl') else 0
        profit_factor = abs(pnl_won / pnl_lost) if pnl_lost != 0 else float('inf')
        return {
            'basic_info': {
                'symbol': self.symbol,
                'initial_capital': initial_capital,
                'final_value': final_value,
                'total_return': total_return,
                'total_trades': total_trades,
            },
            'return_metrics': {
                'total_return_pct': total_return * 100,
                'annual_return_pct': returns_analyzer.get('rnorm100', 0),
                'avg_return_pct': returns_analyzer.get('ravg', 0) * 100,
            },
            'risk_metrics': {
                'max_drawdown_pct': drawdown_analyzer.max.drawdown,
                'max_drawdown_period': drawdown_analyzer.max.len,
                'sharpe_ratio': sharpe_analyzer.get('sharperatio', 0),
            },
            'trade_metrics': {
                'win_rate_pct': win_rate * 100,
                'won_trades': won_trades,
                'lost_trades': lost_trades,
                'profit_factor': profit_factor,
                'avg_win': trades_analyzer.won.pnl.average if hasattr(trades_analyzer.won, 'pnl') else 0,
                'avg_loss': trades_analyzer.lost.pnl.average if hasattr(trades_analyzer.lost, 'pnl') else 0,
            },
            'strategy_data': {
                'trades': strat.trades,
                'signals': strat.signals,
                'ma_values': list(strat.ma20.array),
            }
        }

    def print_backtest_report(self, results: Dict[str, Any]):
        if not results:
            print("没有回测结果")
            return
        basic = results['basic_info']
        returns = results['return_metrics']
        risk = results['risk_metrics']
        trade = results['trade_metrics']
        print("\n" + "="*50)
        print("           回 测 报 告")
        print("="*50)
        print(f"品种: {basic['symbol']}")
        print(f"初始资金: {basic['initial_capital']:,.2f} CNY")
        print(f"最终资产: {basic['final_value']:,.2f} CNY")
        print(f"总收益率: {basic['total_return']*100:+.2f}%")
        print(f"总交易次数: {basic['total_trades']}")
        print(f"\n收益指标:")
        print(f"  年化收益率: {returns['annual_return_pct']:+.2f}%")
        print(f"  平均收益率: {returns['avg_return_pct']:+.2f}%")
        print(f"\n风险指标:")
        print(f"  最大回撤: {risk['max_drawdown_pct']:+.2f}%")
        print(f"  回撤期: {risk['max_drawdown_period']} 天")
        print(f"  夏普比率: {risk['sharpe_ratio']:.2f}")
        print(f"\n交易指标:")
        print(f"  胜率: {trade['win_rate_pct']:.2f}%")
        print(f"  盈利交易: {trade['won_trades']}")
        print(f"  亏损交易: {trade['lost_trades']}")
        print(f"  盈亏比: {trade['profit_factor']:.2f}")
        print(f"  平均盈利: {trade['avg_win']:.2f}")
        print(f"  平均亏损: {trade['avg_loss']:.2f}")
        print("="*50)

