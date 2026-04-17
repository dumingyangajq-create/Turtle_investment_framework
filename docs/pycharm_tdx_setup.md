# PyCharm 配置：通达信本地数据初选池

本文档对应脚本：`scripts/tdx_initial_pool.py`。

## 1. 准备 Python 环境（Windows + PyCharm）

1. 打开 PyCharm，`File -> Open`，选择项目根目录。
2. 打开 `Settings -> Project -> Python Interpreter`。
3. 新建虚拟环境（推荐 Python 3.10+）：
   - `Add Interpreter -> Add Local Interpreter -> Virtualenv`。
4. 在 PyCharm Terminal 执行：

```bash
pip install -r requirements.txt
```

> 如果你只想运行初选池脚本，最少依赖是 `pandas`。

## 2. 准备数据目录

你的通达信路径示例：`F:\newVer\vipdoc`。

脚本会自动读取如下目录（默认）：
- `F:\newVer\vipdoc\sh\lday\*.day`
- `F:\newVer\vipdoc\sz\lday\*.day`

## 3. 准备 FINANCE(39) 映射文件

由于通达信公式里的 `FINANCE(39)` 不在 `.day` 行情文件中，需单独准备一个 CSV（UTF-8）：

文件示例：`F:\newVer\finance39.csv`

```csv
code,finance39
600000,182300000000
000001,254000000000
```

说明：
- `code`：6 位证券代码（不带交易所后缀）
- `finance39`：原始值（脚本会自动计算 `finance39/1e8`）

## 4. 在 PyCharm 配置运行

1. `Run -> Edit Configurations -> + -> Python`。
2. 参数填写：
   - **Script path**: `scripts/tdx_initial_pool.py`
   - **Working directory**: 项目根目录
   - **Parameters**:

```text
--vipdoc F:/newVer/vipdoc --finance39-csv F:/newVer/finance39.csv --output output/initial_pool.csv
```

3. 点击 `Run`。

## 5. 选股条件（已按你的条件实现）

- `VOL > 0`
- `J <= 13`
- `DIFF > 0`
- `0.5 <= 当日振幅 <= 7.1`
- `-2.3 <= 当日涨跌幅 <= 1.95`
- `FINANCE(39)/100000000 >= 10`

指标计算：
- KDJ：`N=9, M1=3, M2=3`
- MACD：`DIFF=EMA(12)-EMA(26), DEA=EMA(DIFF,9), MACD=2*(DIFF-DEA)`

## 6. 输出结果

默认输出：`output/initial_pool.csv`

主要字段：
- `code`
- `trade_date`
- `close`
- `J`
- `DIFF`
- `当日振幅`
- `当日涨跌幅`
- `FINANCE39`
- `FINANCE39_亿`

如果结果为 0 只，先检查：
1. `finance39.csv` 是否完整；
2. 最近交易日是否满足你设置的阈值；
3. `.day` 数据是否是最新更新。

## 7. 二次评分模块（A/B/C/E 加分 + D 扣分）

如果你已经有结构识别后的特征表（每行一只股票），可以直接批量评分：

```bash
python scripts/score_initial_pool.py --input F:/newVer/pool_features.csv --output output/initial_pool_scored.csv
```

核心函数：`scripts/pool_scoring.py::score_stock_candidate(payload)`。

### 必要字段（输入 CSV 列名）

- `stock_code`, `date`, `is_qualified`, `reject_reason`
- `yang_vol_pct`, `breakout_vol_type`, `sum_turnover`
- `max_down_vol`, `avg_up_vol`, `end_down_vol`, `max_up_vol`
- `price_A`, `price_C`
- `kdj_j`, `kline_type`, `close`, `ma11`, `ma32`
- `long_shadow_down_pct`, `long_shadow_kline`, `long_shadow_vol`（可选）
- `gap_type`, `shadow_ratio`, `b_candle_type`, `first_down_ratio`

输出中包含：`final_score`、`rating`、`is_qualified`、`reject_reason` 及模块分数 `A/B/C/E/D_deduct`。
