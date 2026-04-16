"""均线策略回测与参数优化框架（纯 pandas 版本）。"""

from __future__ import annotations

from dataclasses import dataclass
from itertools import product
from math import sqrt
from typing import Callable, Iterable

import pandas as pd


@dataclass(frozen=True)
class BacktestConfig:
    """回测参数。"""

    initial_capital: float = 1_000_000.0
    commission_rate: float = 0.0003
    slippage_rate: float = 0.0002


@dataclass(frozen=True)
class MAParam:
    """双均线参数。"""

    short_window: int
    long_window: int


@dataclass(frozen=True)
class SplitConfig:
    """训练/验证窗口长度。"""

    train_bars: int = 252 * 2
    valid_bars: int = 252
    step_bars: int = 126


def _validate_price_data(price_df: pd.DataFrame) -> None:
    if "close" not in price_df.columns:
        raise ValueError("price_df 必须包含 close 列")
    if len(price_df) < 3:
        raise ValueError("price_df 长度不足，至少需要 3 条")


def _performance_stats(equity_curve: pd.Series) -> dict[str, float]:
    daily_ret = equity_curve.pct_change().fillna(0.0)
    total_return = equity_curve.iloc[-1] / equity_curve.iloc[0] - 1
    ann_return = (1 + total_return) ** (252 / max(len(equity_curve), 1)) - 1
    ann_vol = daily_ret.std(ddof=0) * sqrt(252)
    sharpe = ann_return / ann_vol if ann_vol > 1e-12 else 0.0
    running_max = equity_curve.cummax()
    mdd = (equity_curve / running_max - 1).min()

    return {
        "total_return": float(total_return),
        "ann_return": float(ann_return),
        "ann_vol": float(ann_vol),
        "sharpe": float(sharpe),
        "max_drawdown": float(mdd),
    }


def run_ma_backtest(
    price_df: pd.DataFrame,
    param: MAParam,
    cfg: BacktestConfig | None = None,
) -> dict[str, object]:
    """运行双均线回测。

    参数
    ----
    price_df: 需要包含 close 列，索引建议为交易日。
    param: short_window 必须小于 long_window。
    cfg: 回测交易成本等参数。
    """

    _validate_price_data(price_df)
    cfg = cfg or BacktestConfig()

    if param.short_window >= param.long_window:
        raise ValueError("short_window 必须小于 long_window")

    df = price_df[["close"]].copy()
    df["ret"] = df["close"].pct_change().fillna(0.0)
    df["ma_short"] = df["close"].rolling(param.short_window).mean()
    df["ma_long"] = df["close"].rolling(param.long_window).mean()
    df["raw_signal"] = (df["ma_short"] > df["ma_long"]).astype(float)
    df["position"] = df["raw_signal"].shift(1).fillna(0.0)

    # 换手成本：仓位变化即交易
    turnover = (df["position"] - df["position"].shift(1).fillna(0.0)).abs()
    cost = turnover * (cfg.commission_rate + cfg.slippage_rate)

    df["strategy_ret"] = df["position"] * df["ret"] - cost
    df["equity"] = cfg.initial_capital * (1 + df["strategy_ret"]).cumprod()

    stats = _performance_stats(df["equity"])

    return {
        "param": param,
        "stats": stats,
        "equity_curve": df["equity"],
        "daily_returns": df["strategy_ret"],
    }


def optimize_ma_params(
    price_df: pd.DataFrame,
    short_windows: Iterable[int],
    long_windows: Iterable[int],
    score_fn: Callable[[dict[str, float]], float] | None = None,
    cfg: BacktestConfig | None = None,
) -> tuple[MAParam, pd.DataFrame]:
    """网格搜索参数优化。"""

    _validate_price_data(price_df)
    cfg = cfg or BacktestConfig()
    score_fn = score_fn or (lambda s: s["sharpe"])

    rows: list[dict[str, float]] = []
    best_param: MAParam | None = None
    best_score = float("-inf")

    for sw, lw in product(short_windows, long_windows):
        if sw >= lw:
            continue
        param = MAParam(sw, lw)
        result = run_ma_backtest(price_df, param, cfg)
        stats = result["stats"]
        score = float(score_fn(stats))
        rows.append(
            {
                "short_window": sw,
                "long_window": lw,
                "score": score,
                **stats,
            }
        )

        if score > best_score:
            best_score = score
            best_param = param

    if best_param is None:
        raise ValueError("没有可用参数组合，请检查窗口范围")

    result_df = pd.DataFrame(rows).sort_values("score", ascending=False).reset_index(drop=True)
    return best_param, result_df


def walk_forward_optimize(
    price_df: pd.DataFrame,
    short_windows: Iterable[int],
    long_windows: Iterable[int],
    split_cfg: SplitConfig | None = None,
    bt_cfg: BacktestConfig | None = None,
) -> pd.DataFrame:
    """滚动窗口参数优化，返回每期最优参数及验证集表现。"""

    _validate_price_data(price_df)
    split_cfg = split_cfg or SplitConfig()

    rows: list[dict[str, float]] = []
    start = 0
    while True:
        train_end = start + split_cfg.train_bars
        valid_end = train_end + split_cfg.valid_bars
        if valid_end > len(price_df):
            break

        train_df = price_df.iloc[start:train_end]
        valid_df = price_df.iloc[train_end:valid_end]

        best_param, _ = optimize_ma_params(
            train_df,
            short_windows=short_windows,
            long_windows=long_windows,
            cfg=bt_cfg,
        )
        valid_result = run_ma_backtest(valid_df, best_param, bt_cfg)

        rows.append(
            {
                "start": float(start),
                "train_end": float(train_end),
                "valid_end": float(valid_end),
                "short_window": float(best_param.short_window),
                "long_window": float(best_param.long_window),
                "valid_sharpe": float(valid_result["stats"]["sharpe"]),
                "valid_return": float(valid_result["stats"]["total_return"]),
                "valid_mdd": float(valid_result["stats"]["max_drawdown"]),
            }
        )
        start += split_cfg.step_bars

    return pd.DataFrame(rows)
