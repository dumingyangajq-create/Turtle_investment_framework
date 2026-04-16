import pandas as pd

from scripts.ma_backtest_framework import (
    MAParam,
    optimize_ma_params,
    run_ma_backtest,
    walk_forward_optimize,
)


def _mock_price_df(n: int = 800) -> pd.DataFrame:
    idx = pd.date_range("2020-01-01", periods=n, freq="B")
    # 稳定上行 + 小幅震荡，避免随机性导致测试不稳定
    series = pd.Series(range(n), index=idx).astype(float)
    close = 100 + series * 0.08 + (series % 7) * 0.03
    return pd.DataFrame({"close": close}, index=idx)


def test_run_ma_backtest_outputs_expected_keys():
    df = _mock_price_df()
    result = run_ma_backtest(df, MAParam(short_window=10, long_window=60))

    assert set(result.keys()) == {"param", "stats", "equity_curve", "daily_returns"}
    assert result["param"].short_window == 10
    assert "sharpe" in result["stats"]


def test_optimize_ma_params_returns_valid_best_param_and_sorted_scores():
    df = _mock_price_df()
    best_param, result_df = optimize_ma_params(
        df,
        short_windows=[5, 10, 15],
        long_windows=[30, 60, 90],
    )

    assert best_param.short_window < best_param.long_window
    assert not result_df.empty
    assert result_df["score"].iloc[0] >= result_df["score"].iloc[-1]


def test_walk_forward_optimize_returns_non_empty_result():
    df = _mock_price_df(1000)
    wf = walk_forward_optimize(
        df,
        short_windows=[5, 10],
        long_windows=[30, 60],
    )

    assert not wf.empty
    assert {"valid_sharpe", "valid_return", "valid_mdd"}.issubset(wf.columns)
