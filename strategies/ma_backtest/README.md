# Python 环境下的均线回测 + 参数优化框架

这套框架面向“先可复用、后可扩展”的量化研究流程，核心目标：

1. **环境可复现**：团队成员在任意机器上都能跑出一致结果。
2. **策略可回测**：快速验证双均线策略在历史行情中的收益与回撤。
3. **参数可优化**：通过网格搜索与滚动窗口，减少过拟合风险。

---

## 1) 推荐目录结构

```text
project/
  data/
    raw/                  # 原始行情
    processed/            # 清洗后行情
  scripts/
    ma_backtest_framework.py
  reports/
    backtest/
    optimization/
  notebooks/
    ma_research.ipynb
  requirements.txt
```

---

## 2) Python 环境建议

### A. 快速开始（venv）

```bash
python -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

### B. 可选依赖（做更强优化时）

```bash
pip install optuna plotly
```

> 当前仓库中的 `scripts/ma_backtest_framework.py` 不依赖 optuna；
> 如果后续要做贝叶斯优化，再引入即可。

---

## 3) 参数优化框架设计

建议把参数优化分为三层：

1. **粗筛（Grid Search）**
   - 示例：`short_window in [5, 10, 15, 20]`
   - `long_window in [30, 60, 90, 120]`
2. **稳定性检验（Walk-forward）**
   - 训练集找最优，验证集检验是否稳定。
3. **生产约束过滤**
   - 例如最大回撤阈值、换手率上限、最小交易次数。

### 评分函数建议

默认可以用 Sharpe；更稳健可使用组合评分：

```text
score = sharpe * 0.5 + ann_return * 0.3 - abs(max_drawdown) * 0.2
```

---

## 4) 最小可运行示例

```python
import pandas as pd
from scripts.ma_backtest_framework import (
    BacktestConfig,
    optimize_ma_params,
    run_ma_backtest,
    walk_forward_optimize,
)

price_df = pd.read_csv("data/processed/xxx.csv", parse_dates=["trade_date"]).set_index("trade_date")

best_param, result_df = optimize_ma_params(
    price_df,
    short_windows=[5, 10, 15, 20],
    long_windows=[30, 60, 90, 120],
    cfg=BacktestConfig(initial_capital=1_000_000, commission_rate=0.0003, slippage_rate=0.0002),
)
print("Best:", best_param)
print(result_df.head())

bt = run_ma_backtest(price_df, best_param)
print(bt["stats"])

wf = walk_forward_optimize(
    price_df,
    short_windows=[5, 10, 15, 20],
    long_windows=[30, 60, 90, 120],
)
print(wf.tail())
```

---

## 5) 实战建议

- 不要只看总收益，至少同时看：`Sharpe / Max Drawdown / 换手成本敏感性`。
- 参数边界要有交易逻辑解释，不要“无限扩窗”硬找最优。
- 滚动验证中，如果参数频繁跳变，说明策略稳健性偏弱。
- 每次优化后都落盘（CSV + 图表 + 配置），保证研究可追溯。

---

## 6) 下一步可扩展

- 增加空头与仓位管理（分档仓位而非 0/1 仓位）。
- 加入组合级回测（多标的 + 风险平价）。
- 引入 Optuna/Bayes 进行高维参数搜索。
- 接入自动报告（HTML/PDF），供投研复盘。
