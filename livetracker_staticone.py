import pandas as pd
import streamlit as st
import requests
from datetime import datetime, timedelta
import plotly.graph_objects as go
import os

# -------------------------
# Page Config
# -------------------------
st.set_page_config(page_title="BTC & ETH 7-Day Tracker (Binance)", layout="wide")
st.title("BTC & ETH 7-Day Live Tracker — Binance + CSV Logging + Historical Viewer")

# -------------------------
# Settings
# -------------------------
refresh_interval = 60  # seconds
days_to_track = 7
ema_period = 7
binance_api = "https://api.binance.com/api/v3/klines"

# -------------------------
# Sidebar - Historical Snapshot Viewer
# -------------------------
st.sidebar.header("🧊 Historical Snapshot Viewer")

raw_data_dir = "data_logs/raw_data"
os.makedirs(raw_data_dir, exist_ok=True)

# Find all available snapshot dates
available_files = [f for f in os.listdir(raw_data_dir) if f.endswith(".csv")]
available_dates = sorted(
    list({f.split("_")[-1].split(".")[0] for f in available_files}),
    reverse=True
)

snapshot_choice = st.sidebar.selectbox("📅 Select snapshot date:", ["Today (Live)"] + available_dates)
freeze_mode = snapshot_choice != "Today (Live)"

# -------------------------
# Helper: Fetch Binance Data
# -------------------------
def get_binance_data(symbol, days=7, interval="1h"):
    end_time = datetime.utcnow()
    start_time = end_time - timedelta(days=days)
    url = f"{binance_api}?symbol={symbol}&interval={interval}&startTime={int(start_time.timestamp()*1000)}&endTime={int(end_time.timestamp()*1000)}"
    r = requests.get(url)
    r.raise_for_status()
    data = r.json()

    df = pd.DataFrame(data, columns=[
        "timestamp", "open", "high", "low", "close", "volume",
        "close_time", "qav", "num_trades", "tbbav", "tbqav", "ignore"
    ])
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
    df["price"] = df["close"].astype(float)
    df = df[["timestamp", "price"]]
    df.set_index("timestamp", inplace=True)
    return df

# -------------------------
# Load Data (Live or Frozen)
# -------------------------
if freeze_mode:
    st.sidebar.info(f"🧊 Viewing frozen data from: {snapshot_choice}")
    btc_file = f"{raw_data_dir}/BTCUSDT_{snapshot_choice}.csv"
    eth_file = f"{raw_data_dir}/ETHUSDT_{snapshot_choice}.csv"
    btc_df = pd.read_csv(btc_file, parse_dates=["timestamp"], index_col="timestamp")
    eth_df = pd.read_csv(eth_file, parse_dates=["timestamp"], index_col="timestamp")
else:
    st.sidebar.success("📡 Live mode: fetching latest Binance prices")
    try:
        btc_df = get_binance_data("BTCUSDT", days_to_track)
        eth_df = get_binance_data("ETHUSDT", days_to_track)
    except Exception as e:
        st.error(f"Failed to fetch data: {e}")
        st.stop()

    # Save current data as frozen snapshot
    today_str = datetime.now().strftime("%Y-%m-%d")
    btc_df.to_csv(f"{raw_data_dir}/BTCUSDT_{today_str}.csv")
    eth_df.to_csv(f"{raw_data_dir}/ETHUSDT_{today_str}.csv")

# -------------------------
# Combine BTC + ETH
# -------------------------
data = pd.concat([btc_df["price"], eth_df["price"]], axis=1)
data.columns = ["BTC-USD", "ETH-USD"]
data = data.ffill().bfill()

# -------------------------
# Compute Portfolios (Normalized)
# -------------------------
btc = data["BTC-USD"] / data["BTC-USD"].iloc[0]
eth = data["ETH-USD"] / data["ETH-USD"].iloc[0]
mix = 0.5 * btc + 0.5 * eth

portfolios = pd.DataFrame({
    "100% BTC": btc,
    "100% ETH": eth,
    "50% BTC + 50% ETH (Average)": mix
}, index=data.index)

y_min = portfolios.min().min() * 0.995
y_max = portfolios.max().max() * 1.005

# -------------------------
# Portfolio Chart
# -------------------------
fig_port = go.Figure()
fig_port.add_trace(go.Scatter(x=portfolios.index, y=portfolios["100% BTC"],
                              name="100% BTC", line=dict(width=3, color="#FF9900")))
fig_port.add_trace(go.Scatter(x=portfolios.index, y=portfolios["100% ETH"],
                              name="100% ETH", line=dict(width=3, color="#6A5ACD")))
fig_port.add_trace(go.Scatter(x=portfolios.index, y=portfolios["50% BTC + 50% ETH (Average)"],
                              name="50/50 (Average)", line=dict(width=4, dash="dash", color="black")))

fig_port.update_layout(
    title=f"Portfolio Performance (Last {days_to_track} days, normalized)",
    xaxis_title="Datetime (UTC)",
    yaxis_title="Normalized value (Base = 1.0)",
    template="plotly_white",
    hovermode="x unified",
    height=700,
    font=dict(size=14)
)
fig_port.update_yaxes(range=[y_min, y_max])
st.plotly_chart(fig_port, use_container_width=True)

# -------------------------
# BTC Price + EMA
# -------------------------
btc_price = data["BTC-USD"].copy()
btc_ema = btc_price.ewm(span=ema_period, adjust=False).mean()

fig_btc = go.Figure()
fig_btc.add_trace(go.Scatter(x=btc_price.index, y=btc_price, name="BTC-USD Price", line=dict(width=3, color="orange")))
fig_btc.add_trace(go.Scatter(x=btc_ema.index, y=btc_ema, name=f"{ema_period}-period EMA",
                             line=dict(width=3, color="black", dash="dot")))
fig_btc.update_layout(
    title=f"Bitcoin (BTC-USD) Price (Last {days_to_track} days) & {ema_period}-period EMA",
    xaxis_title="Datetime (UTC)",
    yaxis_title="Price (USD)",
    template="plotly_white",
    hovermode="x unified",
    height=600,
    font=dict(size=14)
)
st.plotly_chart(fig_btc, use_container_width=True)

# -------------------------
# ETH Price + EMA
# -------------------------
eth_price = data["ETH-USD"].copy()
eth_ema = eth_price.ewm(span=ema_period, adjust=False).mean()

fig_eth = go.Figure()
fig_eth.add_trace(go.Scatter(x=eth_price.index, y=eth_price, name="ETH-USD Price", line=dict(width=3, color="purple")))
fig_eth.add_trace(go.Scatter(x=eth_ema.index, y=eth_ema, name=f"{ema_period}-period EMA",
                             line=dict(width=3, color="green", dash="dot")))
fig_eth.update_layout(
    title=f"Ethereum (ETH-USD) Price (Last {days_to_track} days) & {ema_period}-period EMA",
    xaxis_title="Datetime (UTC)",
    yaxis_title="Price (USD)",
    template="plotly_white",
    hovermode="x unified",
    height=600,
    font=dict(size=14)
)
st.plotly_chart(fig_eth, use_container_width=True)

# -------------------------
# Metrics
# -------------------------
eth_last = portfolios["100% ETH"].iloc[-1]
btc_last = portfolios["100% BTC"].iloc[-1]
eth_btc_ratio = eth_last / btc_last
eth_return_pct = (eth_last - 1) * 100
btc_return_pct = (btc_last - 1) * 100
diff_pct = eth_return_pct - btc_return_pct

col1, col2, col3 = st.columns(3)
col1.metric("BTC normalized", f"{btc_last:.4f}", f"{btc_return_pct:.2f}%")
col2.metric("ETH normalized", f"{eth_last:.4f}", f"{eth_return_pct:.2f}%")
col3.metric("ETH/BTC ratio", f"{eth_btc_ratio:.4f}", f"{diff_pct:.2f}%")

if eth_last > btc_last:
    st.success(f"🟢 ETH Recovery Detected — ETH > BTC (ETH/BTC ratio {eth_btc_ratio:.4f})")
else:
    st.warning(f"🔴 BTC Leading — BTC > ETH (ETH/BTC ratio {eth_btc_ratio:.4f})")

# -------------------------
# Data Logging (Daily Summary)
# -------------------------
os.makedirs("data_logs", exist_ok=True)
log_filename = f"data_logs/crypto_tracker_{datetime.now().strftime('%Y-%m-%d')}.csv"

log_entry = pd.DataFrame({
    "timestamp_utc": [datetime.now().strftime("%Y-%m-%d %H:%M:%S")],
    "BTC_Price": [btc_price.iloc[-1]],
    "ETH_Price": [eth_price.iloc[-1]],
    "BTC_Normalized": [btc_last],
    "ETH_Normalized": [eth_last],
    "Mix_50_50": [mix.iloc[-1]],
    "ETH_BTC_Ratio": [eth_btc_ratio],
    "BTC_Return_%": [btc_return_pct],
    "ETH_Return_%": [eth_return_pct],
    "Difference_%": [diff_pct]
})

if not os.path.exists(log_filename):
    log_entry.to_csv(log_filename, index=False)
else:
    log_entry.to_csv(log_filename, mode='a', header=False, index=False)

# -------------------------
# Download Button
# -------------------------
st.download_button(
    label="⬇️ Download Today's CSV Log",
    data=open(log_filename, "rb").read(),
    file_name=os.path.basename(log_filename),
    mime="text/csv",
)

st.success(f"📁 Latest data logged to: {log_filename}")

st.markdown("---")
st.caption("Notes: Portfolio chart is normalized (start = 1.0). Price charts use absolute USD prices and EMAs. Historical data snapshots are frozen once saved.")
