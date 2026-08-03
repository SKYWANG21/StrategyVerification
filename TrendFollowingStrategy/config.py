"""
MA20趋势跟踪策略 - 全局配置文件

【面向初学者】
本文件集中存放策略所需的全部配置：
- 路径（项目根、源码、脚本、结果、日志、数据缓存）
- 数据源（tushare / akshare）及 API 凭证
- 策略参数（MA周期、止损比例等）
- 各期货品种的交易参数（手续费、保证金、合约乘数、滑点）
- 回测参数（起止日期、初始资金、单笔风险、最大仓位）
- 日志与绩效分析相关配置

其他模块通过 get_config()、get_instrument_config(symbol) 等函数读取配置，
避免在代码里写死参数，便于修改和扩展。
"""

import os
import sys
from typing import Dict, Any

# ---------- 路径配置 ----------
# 当前文件所在目录即为策略项目根目录
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
# 仓库根目录（上一级），用于存放 data 等
REPO_ROOT = os.path.dirname(PROJECT_ROOT)
PATHS = {
    'project_root': PROJECT_ROOT,
    'src_dir': os.path.join(PROJECT_ROOT, 'src'),
    'scripts_dir': os.path.join(PROJECT_ROOT, 'scripts'),
    'results_dir': os.path.join(PROJECT_ROOT, 'results'),
    'logs_dir': os.path.join(PROJECT_ROOT, 'logs'),
    'data_dir': os.path.join(REPO_ROOT, 'data'),
    'data_cache_dir': os.path.join(REPO_ROOT, 'data', 'cache'),
}

# ---------- 基础配置（数据、策略、品种、回测、日志） ----------
BASE_CONFIG = {
    # 数据配置
    'data_source': 'akshare',  # 可选 'tushare' 或 'akshare'
    'tushare_token': os.getenv('TUSHARE_TOKEN', ''),  # Tushare 需在环境变量中设置
    'data_cache_dir': PATHS['data_cache_dir'],
    
    # 策略参数
    'ma_period': 20,           # MA 周期，即 MA20
    'max_loss_pct': 0.06,     # 最大止损容忍度 6%（超过则用强制止损）
    'force_stop_pct': 0.03,   # 强制止损比例 3%
    
    # 交易品种配置（主连代码 -> 参数）
    'instruments': {
        'RB0': {  # 螺纹钢主连
            'name': '螺纹钢主连',
            'exchange': 'SHF',
            'commission': 0.0003,       # 手续费 万分之三
            'margin_rate': 0.10,        # 保证金比例 10%
            'contract_multiplier': 10,  # 合约乘数（每手对应 10 吨等）
            'slippage': 0.001,         # 滑点 0.1%
        },
        'CU0': {  # 铜主连
            'name': '铜主连',
            'exchange': 'SHF',
            'commission': 0.00005,
            'margin_rate': 0.08,
            'contract_multiplier': 5,
            'slippage': 0.001,
        },
        'IF0': {  # 沪深300主连
            'name': '沪深300主连',
            'exchange': 'CFFEX',
            'commission': 0.000023,
            'margin_rate': 0.12,
            'contract_multiplier': 300,
            'slippage': 0.001,
        }
    },
    
    # 回测配置
    'backtest': {
        'start_date': '2024-01-01',
        'end_date': '2025-12-31',
        'initial_capital': 100000,   # 初始资金（元）
        'risk_per_trade': 0.02,      # 每笔交易风险占资金 2%
        'max_position_size': 0.8,    # 最大仓位 80%
    },
    
    # 日志配置
    'logging': {
        'level': 'INFO',
        'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        'file': os.path.join(PATHS['logs_dir'], 'strategy.log'),
    },
    'paths': PATHS
}

# ---------- 2日K线合成规则 ----------
# resample 时各列采用的聚合方式：open 取第一根，high 取最大，low 取最小，close 取最后一根，volume/amount 求和
RESAMPLE_CONFIG = {
    'target_period': '2D',
    'aggregation_rules': {
        'open': 'first',
        'high': 'max',
        'low': 'min',
        'close': 'last',
        'volume': 'sum',
        'amount': 'sum',
    }
}

# ---------- 绩效分析要计算的指标与是否绘图 ----------
ANALYSIS_CONFIG = {
    'indicators': [
        'total_return', 'annual_return', 'sharpe_ratio', 'max_drawdown',
        'win_rate', 'profit_factor', 'trade_count', 'avg_holding_days'
    ],
    'visualization': {
        'equity_curve': True,
        'drawdown_chart': True,
        'trade_distribution': True,
        'monthly_returns': True,
    }
}


def get_config(section: str = None) -> Dict[str, Any]:
    """获取配置。不传 section 则返回全部 BASE_CONFIG；传了则返回该段（如 'backtest'）。"""
    if section is None:
        return BASE_CONFIG
    return BASE_CONFIG.get(section, {})


def get_instrument_config(symbol: str) -> Dict[str, Any]:
    """根据品种代码（如 'RB0'）获取该品种的手续费、保证金、合约乘数等。"""
    return BASE_CONFIG['instruments'].get(symbol, {})


def validate_config() -> bool:
    """校验配置是否有效（如 Tushare 时是否有 token，止损比例是否为正等）。"""
    if BASE_CONFIG['data_source'] == 'tushare' and not BASE_CONFIG['tushare_token']:
        print("警告: Tushare token未设置，请设置环境变量TUSHARE_TOKEN")
        return False
    if BASE_CONFIG['ma_period'] <= 0:
        print("错误: MA周期必须大于0")
        return False
    if BASE_CONFIG['max_loss_pct'] <= 0 or BASE_CONFIG['force_stop_pct'] <= 0:
        print("错误: 止损比例必须大于0")
        return False
    return True

def get_paths() -> Dict[str, str]:
    """返回路径字典，供其他模块写结果、日志、缓存等。"""
    return PATHS


def ensure_directories() -> None:
    """确保配置中的各目录存在，不存在则创建。"""
    for key in ['src_dir', 'scripts_dir', 'results_dir', 'logs_dir', 'data_dir', 'data_cache_dir']:
        os.makedirs(PATHS[key], exist_ok=True)


def add_sys_path() -> None:
    """把项目根、src、scripts 加入 sys.path，便于各脚本 import 项目模块。"""
    paths_to_add = [PROJECT_ROOT, PATHS['src_dir'], PATHS['scripts_dir']]
    for p in paths_to_add:
        if p not in sys.path:
            sys.path.insert(0, p)


# 模块加载时自动执行：加入路径并创建目录
add_sys_path()
ensure_directories()
