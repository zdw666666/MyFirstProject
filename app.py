import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np

st.title("📊 多资产凯利实盘系统（稳定版）")

# ===== 参数 =====
target_vol = 0.15
kelly_scale = 0.3
total_capital = 10000000  # 1000万

assets = {
    "黄金(GLD)": "GLD",
    "纳指(QQQ)": "QQQ",
    "A股(ASHR)": "ASHR",
    "美债(TLT)": "TLT",
    "美元(UUP)": "UUP"
}

# ===== 核心函数 =====
def calc_asset(symbol):
    try:
        df = yf.download(symbol, period="6mo", progress=False)

        # 防止数据问题
        if df.empty or len(df) < 100:
            return None

        df['MA50'] = df['Close'].rolling(50).mean()
        df['MA100'] = df['Close'].rolling(100).mean()

        df['EMA12'] = df['Close'].ewm(span=12).mean()
        df['EMA26'] = df['Close'].ewm(span=26).mean()
        df['DIF'] = df['EMA12'] - df['EMA26']
        df['DEA'] = df['DIF'].ewm(span=9).mean()

        df['ret'] = df['Close'].pct_change()
        vol = df['ret'].std() * np.sqrt(252)

        df = df.dropna()
        if df.empty:
            return None

        latest = df.iloc[-1]

        # ===== 趋势 =====
        if latest['Close'] > latest['MA50'] and latest['Close'] > latest['MA100']:
            T = 0.1
        elif latest['Close'] > latest['MA50']:
            T = 0.05
        else:
            T = -0.1

        # ===== 动量 =====
        if latest['DIF'] > latest['DEA'] and latest['DIF'] > 0:
            M = 0.08
        elif latest['DIF'] > latest['DEA']:
            M = 0.05
        else:
            M = -0.08

        # ===== 胜率 =====
        p = 0.5 + T + M

        # ===== 凯利 =====
        b = 1.2
        f = (p * (b + 1) - 1) / b

        # ===== 波动率控制 =====
        if vol and vol > 0:
            f = f * (target_vol / vol)

        # ===== 凯利打折 =====
        f = f * kelly_scale

        return {
            "资产": symbol,
            "胜率": round(p, 3),
            "凯利": f,
            "波动率": round(vol, 3)
        }

    except Exception as e:
        return None


# ===== 主流程 =====
results = []

for name, ticker in assets.items():
    data = calc_asset(ticker)
    if data is None:
        continue

    data["资产"] = name
    results.append(data)

if len(results) == 0:
    st.error("⚠️ 数据获取失败，请稍后再试")
    st.stop()

df = pd.DataFrame(results)

# ===== 只保留正凯利 =====
df = df[df['凯利'] > 0]

if df.empty:
    st.warning("当前无可交易资产（全部负凯利）")
    st.stop()

# ===== 风险平价 =====
df['风险权重'] = 1 / df['波动率']
df['风险权重'] = df['风险权重'] / df['风险权重'].sum()

# ===== 综合权重 =====
df['最终权重'] = df['风险权重'] * df['凯利']
df['最终权重'] = df['最终权重'] / df['最终权重'].sum()

# ===== 市场过滤 =====
avg_p = df['胜率'].mean()

if avg_p < 0.5:
    total_position = 0.1
elif avg_p < 0.55:
    total_position = 0.3
else:
    total_position = 0.6

# ===== 最终仓位 =====
df['仓位'] = df['最终权重'] * total_position
df['资金(元)'] = (df['仓位'] * total_capital).round(0)

# ===== 显示结果 =====
st.dataframe(df)

st.subheader(f"👉 总仓位：{round(df['仓位'].sum()*100,1)}%")

# ===== 市场状态 =====
if avg_p < 0.5:
    st.error("市场弱势：建议观望")
elif avg_p < 0.55:
    st.warning("中性市场：轻仓试探")
else:
    st.success("趋势市场：可以加仓")
