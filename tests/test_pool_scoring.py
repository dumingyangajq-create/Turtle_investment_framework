from scripts.pool_scoring import score_stock_candidate


def test_score_stock_candidate_unqualified():
    result = score_stock_candidate(
        {
            "stock_code": "600000",
            "date": "2026-04-17",
            "is_qualified": False,
            "reject_reason": "跌破结构",
        }
    )
    assert result["final_score"] == 0.0
    assert result["rating"] == "D级（不合格）"
    assert result["reject_reason"] == "跌破结构"


def test_score_stock_candidate_full_path():
    payload = {
        "stock_code": "600000",
        "date": "2026-04-17",
        "is_qualified": True,
        "yang_vol_pct": 66,
        "breakout_vol_type": "递增放量",
        "sum_turnover": 24,
        "max_down_vol": 80,
        "avg_up_vol": 200,
        "end_down_vol": 40,
        "max_up_vol": 220,
        "price_A": 10,
        "price_C": 10.5,
        "kdj_j": -1,
        "kline_type": "带下影小阳线",
        "close": 10.5,
        "ma11": 10.2,
        "ma32": 9.8,
        "long_shadow_down_pct": -8.5,
        "long_shadow_kline": "带下影线",
        "gap_type": "无跳空",
        "shadow_ratio": 1.2,
        "b_candle_type": "阳线",
        "first_down_ratio": 0.4,
    }
    result = score_stock_candidate(payload)

    # A=30, B=35, C=15, E=18, D=0 => 98
    assert result["final_score"] == 98.0
    assert result["rating"] == "S级（钻石买点）"
    assert result["module_scores"] == {
        "A": 30.0,
        "B": 35.0,
        "C": 15.0,
        "E": 18.0,
        "D_deduct": 0.0,
    }


def test_score_stock_candidate_d_deduct_cap_20():
    payload = {
        "stock_code": "000001",
        "date": "2026-04-17",
        "is_qualified": True,
        "yang_vol_pct": 65,
        "breakout_vol_type": "递增放量",
        "sum_turnover": 24,
        "max_down_vol": 80,
        "avg_up_vol": 200,
        "end_down_vol": 40,
        "max_up_vol": 220,
        "price_A": 10,
        "price_C": 10.2,
        "kdj_j": 9,
        "kline_type": "十字星",
        "close": 10.2,
        "ma11": 10.3,
        "ma32": 10.0,
        "long_shadow_down_pct": -3,
        "long_shadow_kline": "其他",
        "gap_type": "末期跳空",
        "shadow_ratio": 5,
        "b_candle_type": "阴线",
        "first_down_ratio": 0.95,
    }
    result = score_stock_candidate(payload)
    assert result["module_scores"]["D_deduct"] == 20.0
