import streamlit as st
import time
from iv_crush_bot import DeltaIVCrushBot
import pandas as pd
from datetime import datetime

st.set_page_config(page_title="IV Crush Bot 🚀", layout="wide", page_icon="📈")

st.markdown("""
<style>
    .main {background-color: #0e1117;}
    .stMetric {background-color: #1e2130; padding: 15px; border-radius: 10px;}
    h1 {color: #00d4ff; text-align: center;}
    .success-box {background: #1e4620; padding: 10px; border-radius: 5px; border-left: 4px solid #00ff00;}
    .warning-box {background: #4a3520; padding: 10px; border-radius: 5px; border-left: 4px solid #ffa500;}
</style>
""", unsafe_allow_html=True)

if 'bot' not in st.session_state:
    API_KEY = "TLRiOUwfrMG1gWmeg897cDbCnCOjcQ"
    API_SECRET = "Ws8eZKD2EyjaJJPzeBuaT9f0MQtUJu3ThRlLqGLTXS60UqfDmOJR58on7RXp"
    st.session_state.bot = DeltaIVCrushBot(API_KEY, API_SECRET, testnet=True)

if 'auto_trade' not in st.session_state:
    st.session_state.auto_trade = False
    
if 'last_check' not in st.session_state:
    st.session_state.last_check = datetime.now()

bot = st.session_state.bot

st.markdown("<h1>🎯 IV Crush Reversal Bot</h1>", unsafe_allow_html=True)
st.markdown("---")

with st.sidebar:
    st.header("⚙️ Settings")
    st.subheader("Strategy Parameters")
    bot.IV_SPIKE_PCT = st.slider("IV Spike %", 5, 20, 10)
    bot.PROTECTION_WIDTH_PCT = st.slider("Protection Width %", 1.0, 5.0, 3.0, 0.5)
    bot.TARGET_PROFIT_PCT = st.slider("Target Profit %", 20, 60, 40)
    bot.RISK_PER_TRADE_PCT = st.slider("Risk Per Trade %", 0.5, 3.0, 1.5, 0.1) / 100
    
    st.markdown("---")
    st.subheader("Auto Trading")
    
    if st.button("🟢 Start Auto Trade" if not st.session_state.auto_trade else "🔴 Stop Auto Trade"):
        st.session_state.auto_trade = not st.session_state.auto_trade
    
    st.caption("Auto checks every 30 seconds")
    
    if st.button("🔄 Refresh Data"):
        st.rerun()

col1, col2, col3, col4 = st.columns(4)

stats = bot.get_stats()
btc_price = bot.get_btc_price() or 0

with col1:
    st.metric("💰 Balance", f"${stats['balance']:,.2f}", 
              f"${stats['total_pnl']:,.2f}" if stats['total_pnl'] != 0 else None)

with col2:
    st.metric("📊 Total Trades", stats['total_trades'])

with col3:
    st.metric("✅ Win Rate", f"{stats['win_rate']:.1f}%")

with col4:
    st.metric("🎯 Open Positions", stats['open_positions'])

st.markdown("---")

# TradingView Chart
col_chart, col_tf = st.columns([4, 1])
with col_chart:
    st.subheader("📊 Live BTC Chart")
with col_tf:
    timeframe = st.selectbox("Timeframe", ["1", "5", "15", "30", "60", "240", "D"], index=1, label_visibility="collapsed")

tradingview_html = f"""
<div class="tradingview-widget-container" style="height:400px;">
  <div id="tradingview_chart" style="height:100%;"></div>
  <script type="text/javascript" src="https://s3.tradingview.com/tv.js"></script>
  <script type="text/javascript">
  new TradingView.widget({{
    "width": "100%",
    "height": 400,
    "symbol": "BINANCE:BTCUSDT",
    "interval": "{timeframe}",
    "timezone": "Etc/UTC",
    "theme": "dark",
    "style": "1",
    "locale": "en",
    "toolbar_bg": "#f1f3f6",
    "enable_publishing": false,
    "hide_top_toolbar": false,
    "save_image": false,
    "container_id": "tradingview_chart"
  }});
  </script>
</div>
"""
st.components.v1.html(tradingview_html, height=420)

st.markdown("---")

col1, col2 = st.columns(2)

with col1:
    st.subheader("📈 Market Data")
    
    market_data = {
        "BTC Price": f"${btc_price:,.2f}",
        "Last Check": st.session_state.last_check.strftime("%H:%M:%S"),
        "Auto Trade": "🟢 Active" if st.session_state.auto_trade else "🔴 Inactive"
    }
    
    for key, val in market_data.items():
        st.text(f"{key}: {val}")

with col2:
    st.subheader("🔍 Entry Signal")
    
    entry_ready, signal = bot.check_entry_conditions()
    
    if signal:
        st.text(f"ATM IV: {signal.get('atm_iv', 0):.1f}%")
        st.text(f"Rolling IV: {signal.get('rolling_iv', 0):.1f}%")
        
        if signal.get('iv_spike'):
            st.markdown('<div class="success-box">✅ IV Spike Detected</div>', unsafe_allow_html=True)
        else:
            st.markdown('<div class="warning-box">⏳ No IV Spike</div>', unsafe_allow_html=True)
        
        if signal.get('sweep'):
            st.markdown('<div class="success-box">✅ Liquidity Sweep</div>', unsafe_allow_html=True)
        else:
            st.markdown('<div class="warning-box">⏳ No Sweep</div>', unsafe_allow_html=True)
    else:
        st.warning("Unable to fetch market data")

st.markdown("---")
col1, col2, col3 = st.columns(3)

with col1:
    if st.button("🎲 Check Entry Signal", use_container_width=True):
        entry_ready, signal = bot.check_entry_conditions()
        if entry_ready:
            st.success("✅ Entry conditions met!")
        else:
            st.info("⏳ Waiting for signal...")
        st.session_state.last_check = datetime.now()

with col2:
    if st.button("📥 Open Position", use_container_width=True):
        entry_ready, signal = bot.check_entry_conditions()
        if entry_ready or True:
            pos = bot.open_credit_spread("BTC", btc_price)
            st.success(f"✅ Opened position #{pos['id']}")
            st.rerun()
        else:
            st.warning("Entry conditions not met")

with col3:
    if st.button("🔄 Manage Positions", use_container_width=True):
        bot.manage_positions()
        st.success("✅ Positions updated")
        st.rerun()

st.markdown("---")
st.subheader("📋 Open Positions")

open_positions = [p for p in bot.positions if p['status'] == 'open']

if open_positions:
    pos_data = []
    for p in open_positions:
        time_in = (datetime.now() - p['entry_time']).total_seconds() / 60
        pos_data.append({
            "ID": p['id'],
            "Entry Price": f"${p['spot_price']:,.0f}",
            "Sell Strike": f"${p['sell_strike']:,.0f}",
            "Buy Strike": f"${p['buy_strike']:,.0f}",
            "Credit": f"${p['net_credit']:,.2f}",
            "Contracts": p['contracts'],
            "Time (min)": f"{time_in:.1f}",
            "Max Loss": f"${p['max_loss'] * p['contracts']:,.2f}"
        })
    
    st.dataframe(pd.DataFrame(pos_data), use_container_width=True, hide_index=True)
else:
    st.info("No open positions")

st.markdown("---")
st.subheader("📜 Trade History")

closed_positions = [p for p in bot.positions if p['status'] == 'closed'][-10:]

if closed_positions:
    history_data = []
    for p in closed_positions:
        history_data.append({
            "ID": p['id'],
            "Entry": p['entry_time'].strftime("%H:%M"),
            "Exit": p.get('exit_time', datetime.now()).strftime("%H:%M"),
            "Entry Price": f"${p['spot_price']:,.0f}",
            "Exit Reason": p.get('exit_reason', 'N/A'),
            "Time (min)": f"{p.get('time_in_trade', 0):.1f}",
            "P&L": f"${p['pnl']:,.2f}",
            "Status": "✅" if p['pnl'] > 0 else "❌"
        })
    
    df = pd.DataFrame(history_data)
    st.dataframe(df, use_container_width=True, hide_index=True)
else:
    st.info("No trade history yet")

if st.session_state.auto_trade:
    with st.spinner("Auto trading active..."):
        entry_ready, _ = bot.check_entry_conditions()
        if entry_ready and stats['open_positions'] < 3:
            bot.open_credit_spread("BTC", btc_price)
            st.toast("✅ New position opened!", icon="🎯")
        
        bot.manage_positions()
        st.session_state.last_check = datetime.now()
        
        time.sleep(1)
        st.rerun()

st.markdown("---")
st.caption("⚠️ Testnet Mode | Built for educational purposes | Not financial advice")
