# import streamlit as st
# import yfinance as yf
# import pandas as pd
# import numpy as np

# st.title("📊 多资产凯利实盘系统（稳定版）")

# # ===== 参数 =====
# target_vol = 0.15
# kelly_scale = 0.3
# total_capital = 10000000  # 1000万

# assets = {
#     "黄金(GLD)": "GLD",
#     "纳指(QQQ)": "QQQ",
#     "A股(ASHR)": "ASHR",
#     "美债(TLT)": "TLT",
#     "美元(UUP)": "UUP"
# }

# # ===== 核心函数 =====
# def calc_asset(symbol):
#     try:
#         df = yf.download(symbol, period="6mo", progress=False)

#         # 防止数据问题
#         if df.empty or len(df) < 100:
#             return None

#         df['MA50'] = df['Close'].rolling(50).mean()
#         df['MA100'] = df['Close'].rolling(100).mean()

#         df['EMA12'] = df['Close'].ewm(span=12).mean()
#         df['EMA26'] = df['Close'].ewm(span=26).mean()
#         df['DIF'] = df['EMA12'] - df['EMA26']
#         df['DEA'] = df['DIF'].ewm(span=9).mean()

#         df['ret'] = df['Close'].pct_change()
#         vol = df['ret'].std() * np.sqrt(252)

#         df = df.dropna()
#         if df.empty:
#             return None

#         latest = df.iloc[-1]

#         # ===== 趋势 =====
#         if latest['Close'] > latest['MA50'] and latest['Close'] > latest['MA100']:
#             T = 0.1
#         elif latest['Close'] > latest['MA50']:
#             T = 0.05
#         else:
#             T = -0.1

#         # ===== 动量 =====
#         if latest['DIF'] > latest['DEA'] and latest['DIF'] > 0:
#             M = 0.08
#         elif latest['DIF'] > latest['DEA']:
#             M = 0.05
#         else:
#             M = -0.08

#         # ===== 胜率 =====
#         p = 0.5 + T + M

#         # ===== 凯利 =====
#         b = 1.2
#         f = (p * (b + 1) - 1) / b

#         # ===== 波动率控制 =====
#         if vol and vol > 0:
#             f = f * (target_vol / vol)

#         # ===== 凯利打折 =====
#         f = f * kelly_scale

#         return {
#             "资产": symbol,
#             "胜率": round(p, 3),
#             "凯利": f,
#             "波动率": round(vol, 3)
#         }

#     except Exception as e:
#         return None


# # ===== 主流程 =====
# results = []

# for name, ticker in assets.items():
#     data = calc_asset(ticker)
#     if data is None:
#         continue

#     data["资产"] = name
#     results.append(data)

# if len(results) == 0:
#     st.error("⚠️ 数据获取失败，请稍后再试")
#     st.stop()

# df = pd.DataFrame(results)

# # ===== 只保留正凯利 =====
# df = df[df['凯利'] > 0]

# if df.empty:
#     st.warning("当前无可交易资产（全部负凯利）")
#     st.stop()

# # ===== 风险平价 =====
# df['风险权重'] = 1 / df['波动率']
# df['风险权重'] = df['风险权重'] / df['风险权重'].sum()

# # ===== 综合权重 =====
# df['最终权重'] = df['风险权重'] * df['凯利']
# df['最终权重'] = df['最终权重'] / df['最终权重'].sum()

# # ===== 市场过滤 =====
# avg_p = df['胜率'].mean()

# if avg_p < 0.5:
#     total_position = 0.1
# elif avg_p < 0.55:
#     total_position = 0.3
# else:
#     total_position = 0.6

# # ===== 最终仓位 =====
# df['仓位'] = df['最终权重'] * total_position
# df['资金(元)'] = (df['仓位'] * total_capital).round(0)

# # ===== 显示结果 =====
# st.dataframe(df)

# st.subheader(f"👉 总仓位：{round(df['仓位'].sum()*100,1)}%")

# # ===== 市场状态 =====
# if avg_p < 0.5:
#     st.error("市场弱势：建议观望")
# elif avg_p < 0.55:
#     st.warning("中性市场：轻仓试探")
# else:
#     st.success("趋势市场：可以加仓")

import streamlit as st
import pandas as pd
import numpy as np
import akshare as ak
from alpha_vantage.timeseries import TimeSeries

# ==========================================
# 1. 核心配置 (请在此处修改参数)
# ==========================================
AV_API_KEY = "O6S7KJJ5AOOHN6TE"  # 👈 填入你的免费 Key
TOTAL_CAPITAL = 10000000  # 1000万实盘资金
TARGET_VOL = 0.12  # 目标波动率 (建议10%-15%之间)
KELLY_SCALE = 0.3  # 凯利缩放 (0.3代表3成凯利，防黑天鹅)
ATR_STOP_MULT = 2.0  # ATR熔断倍数 (2倍ATR跌幅强制平仓)

st.set_page_config(page_title="Gemini 1000W 智投系统", layout="wide")

# 资产配置定义
ASSETS_CONFIG = {
    "纳指(QQQ)": {"ticker": "QQQ", "source": "alpha_vantage"},
    "黄金(GLD)": {"ticker": "GLD", "source": "alpha_vantage"},
    "美债(TLT)": {"ticker": "TLT", "source": "alpha_vantage"},
    "中证1000": {"ticker": "000852", "source": "akshare"},
    "标普500(SPY)": {"ticker": "SPY", "source": "alpha_vantage"}
}


# ==========================================
# 2. 数据引擎：多源接入与缓存
# ==========================================
@st.cache_data(ttl=3600)
def get_market_data(name, config):
    try:
        if config["source"] == "alpha_vantage":
            ts = TimeSeries(key=AV_API_KEY, output_format='pandas')
            df, _ = ts.get_daily_adjusted(symbol=config["ticker"], outputsize='compact')
            df = df.rename(columns={
                "1. open": "Open", "2. high": "High", "3. low": "Low",
                "4. close": "Close", "5. adjusted close": "Adj_Close", "6. volume": "Volume"
            })
            df.index = pd.to_datetime(df.index)
            return df.sort_index()

        elif config["source"] == "akshare":
            df = ak.index_zh_a_hist(symbol=config["ticker"], period="daily")
            df = df.rename(columns={"日期": "Date", "开盘": "Open", "收盘": "Close", "最高": "High", "最低": "Low"})
            df.index = pd.to_datetime(df.Date)
            return df.sort_index()
    except Exception as e:
        st.error(f"无法获取 {name} 数据: {e}")
        return None


# ==========================================
# 3. 策略核心：趋势、动量、ATR熔断
# ==========================================
def calculate_kelly_strategy(df):
    if df is None or len(df) < 60: return None

    # 指标计算
    df['MA50'] = df['Close'].rolling(50).mean()
    df['MA100'] = df['Close'].rolling(100).mean()

    # ATR 计算 (20日平均真实波幅)
    df['H-L'] = df['High'] - df['Low']
    df['H-PC'] = abs(df['High'] - df['Close'].shift(1))
    df['L-PC'] = abs(df['Low'] - df['Close'].shift(1))
    df['TR'] = df[['H-L', 'H-PC', 'L-PC']].max(axis=1)
    df['ATR'] = df['TR'].rolling(20).mean()

    # MACD 计算
    ema12 = df['Close'].ewm(span=12, adjust=False).mean()
    ema26 = df['Close'].ewm(span=26, adjust=False).mean()
    df['DIF'] = ema12 - ema26
    df['DEA'] = df['DIF'].ewm(span=9, adjust=False).mean()

    # 年化波动率
    df['ret'] = df['Close'].pct_change()
    vol = df['ret'].std() * np.sqrt(252)

    latest = df.iloc[-1]
    prev = df.iloc[-2]

    # --- 🚨 核心逻辑：ATR熔断检测 ---
    # 今日跌幅 > 前日ATR的N倍 -> 触发熔断
    is_meltdown = (prev['Close'] - latest['Close']) > (ATR_STOP_MULT * prev['ATR'])

    # 评分系统
    T = 0.1 if (latest['Close'] > latest['MA50'] and latest['Close'] > latest['MA100']) else \
        0.05 if (latest['Close'] > latest['MA50']) else -0.1

    M = 0.08 if (latest['DIF'] > latest['DEA'] and latest['DIF'] > 0) else \
        0.05 if (latest['DIF'] > latest['DEA']) else -0.08

    p = 0.5 + T + M

    # 熔断惩罚：胜率强行置低
    current_status = "✅ 正常"
    if is_meltdown:
        p = 0.35
        current_status = "🚨 熔断"

    # 凯利计算 (盈亏比b设为稳健型1.2)
    b = 1.2
    kelly_f = (p * (b + 1) - 1) / b

    # 波动率平价控仓
    if vol > 0:
        kelly_f *= (TARGET_VOL / vol)

    return {
        "状态": current_status,
        "价格": latest['Close'],
        "胜率预期": round(p, 3),
        "年化波动": round(vol, 3),
        "原始凯利": round(kelly_f, 3)
    }


# ==========================================
# 4. UI 展现与自动资金分配
# ==========================================
st.sidebar.header("⚙️ 实时参数调整")
kelly_scale_adj = st.sidebar.slider("凯利缩放比例", 0.1, 1.0, KELLY_SCALE)

all_results = []
for name, cfg in ASSETS_CONFIG.items():
    data = get_market_data(name, cfg)
    res = calculate_kelly_strategy(data)
    if res:
        res["资产"] = name
        all_results.append(res)

if all_results:
    df_res = pd.DataFrame(all_results)

    # 仅保留正凯利值资产进入分配
    trade_df = df_res[df_res['原始凯利'] > 0].copy()

    if not trade_df.empty:
        # 风险平价权重分配
        trade_df['风险权重'] = 1 / trade_df['年化波动']
        sum_risk_w = trade_df['风险权重'].sum()
        trade_df['最终权重'] = (trade_df['风险权重'] / sum_risk_w) * trade_df['原始_凯利'] * kelly_scale_adj

        # 资金计算
        trade_df['分配金额(万)'] = (trade_df['最终权重'] * TOTAL_CAPITAL / 10000).round(2)

        st.subheader("📊 实时实盘建议 (1000W 基准)")
        st.dataframe(trade_df[['资产', '价格', '状态', '胜率预期', '年化波动', '最终权重', '分配金额(万)']],
                     use_container_width=True)

        # 自动避风港计算
        invested_total = trade_df['最终权重'].sum()
        cash_ratio = max(0, 1 - invested_total)

        col1, col2 = st.columns(2)
        col1.metric("系统总仓位", f"{round(invested_total * 100, 2)}%")
        col2.metric("避风港(SGOV/现金)金额", f"{round(cash_ratio * TOTAL_CAPITAL / 10000, 2)} 万")

        if invested_total < 0.2:
            st.warning("⚠️ 市场极端不稳定，ATR 熔断或趋势走坏，资金已自动撤回避风港。")
    else:
        st.error("❌ 全市场无正期望信号，建议 100% 现金避险。")

st.info("注：ATR 熔断机制会自动识别类似今日黄金、中证1000的异常暴跌并强制剔除。")

