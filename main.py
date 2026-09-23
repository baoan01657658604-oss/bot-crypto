import os
import time
import requests
import pandas as pd
import pandas_ta as ta
from flask import Flask
from threading import Thread

# ==========================================
# 1. KHỞI TẠO FLASK WEB SERVER (KEEP ALIVE)
# ==========================================
app = Flask('')

@app.route('/')
def home():
    return "Bot Donchian Breakout đang hoạt động 24/7!"

def run_server():
    # Render sẽ tự cấp cổng qua biến môi trường PORT (mặc định 8080 nếu chạy local)
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run_server)
    t.daemon = True
    t.start()

# ==========================================
# 2. CẤU HÌNH BOT TRADING & DISCORD WEBHOOK
# ==========================================
DISCORD_WEBHOOK_URL = "https://discord.com/api/webhooks/1344265934149025803/H3iUOFUOR84XD_Uo6WLNq9jhjXD5WOxr8rFwDAnUDsUogdpqDkDnsEnaYC10VQ8O8XTU"

SYMBOL = "BTCUSDT"
TIMEFRAME = "4h"
DONCHIAN_PERIOD = 20
EMA_FILTER_PERIOD = 200
VOLUME_MA_PERIOD = 20
VOLUME_MULTIPLIER = 1.2

# Trạng thái giả lập vị thế (None, "LONG", "SHORT")
current_position = None

def send_discord(message):
    data = {"content": message}
    try:
        response = requests.post(DISCORD_WEBHOOK_URL, json=data)
        if response.status_code == 204:
            print("📣 Đã gửi thông báo Discord thành công!")
        else:
            print(f"❌ Lỗi gửi Discord: {response.status_code}")
    except Exception as e:
        print(f"❌ Lỗi kết nối Discord: {e}")

def get_klines(symbol, interval, limit=300):
    url = f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval={interval}&limit={limit}"
    try:
        res = requests.get(url, timeout=10)
        data = res.json()
        df = pd.DataFrame(data, columns=[
            'open_time', 'open', 'high', 'low', 'close', 'volume',
            'close_time', 'qav', 'num_trades', 'taker_base_vol', 'taker_quote_vol', 'ignore'
        ])
        df['close'] = df['close'].astype(float)
        df['high'] = df['high'].astype(float)
        df['low'] = df['low'].astype(float)
        df['volume'] = df['volume'].astype(float)
        return df
    except Exception as e:
        print(f"❌ Lỗi lấy dữ liệu nến Binance: {e}")
        return None

def analyze_and_trade():
    global current_position
    df = get_klines(SYMBOL, TIMEFRAME)
    if df is None or df.empty:
        return

    # Tính toán các chỉ báo kỹ thuật
    df['ema200'] = ta.ema(df['close'], length=EMA_FILTER_PERIOD)
    donchian = ta.donchian(df['high'], df['low'], lower_length=DONCHIAN_PERIOD, upper_length=DONCHIAN_PERIOD)
    
    # Tìm đúng tên cột Donchian Channel
    dc_upper_col = [c for c in donchian.columns if c.startswith('DCU')][0]
    dc_lower_col = [c for c in donchian.columns if c.startswith('DCL')][0]
    
    df['dc_upper'] = donchian[dc_upper_col]
    df['dc_lower'] = donchian[dc_lower_col]
    df['vol_ma'] = ta.sma(df['volume'], length=VOLUME_MA_PERIOD)

    # Lấy giá trị của nến đã đóng gần nhất (nến -2)
    last_close = df['close'].iloc[-2]
    last_ema200 = df['ema200'].iloc[-2]
    prev_upper = df['dc_upper'].iloc[-3]  # Upper channel nến trước đó
    prev_lower = df['dc_lower'].iloc[-3]  # Lower channel nến trước đó
    last_vol = df['volume'].iloc[-2]
    last_vol_ma = df['vol_ma'].iloc[-2]

    # Điều kiện Volume
    volume_passed = last_vol > (last_vol_ma * VOLUME_MULTIPLIER)

    # Điều kiện Tín hiệu
    long_signal = (last_close > prev_upper) and (last_close > last_ema200) and volume_passed
    short_signal = (last_close < prev_lower) and (last_close < last_ema200) and volume_passed

    if long_signal and current_position != "LONG":
        current_position = "LONG"
        msg = f"🚀 **TÍN HIỆU MUA (LONG) - {SYMBOL} ({TIMEFRAME})**\n- Giá đóng cửa: {last_close}\n- EMA200: {last_ema200:.2f}\n- Donchian Upper: {prev_upper}\n- Khối lượng: Đạt chuẩn (>120% MA20)"
        send_discord(msg)

    elif short_signal and current_position != "SHORT":
        current_position = "SHORT"
        msg = f"🔻 **TÍN HIỆU BÁN (SHORT) - {SYMBOL} ({TIMEFRAME})**\n- Giá đóng cửa: {last_close}\n- EMA200: {last_ema200:.2f}\n- Donchian Lower: {prev_lower}\n- Khối lượng: Đạt chuẩn (>120% MA20)"
        send_discord(msg)

# ==========================================
# 3. CHƯƠNG TRÌNH CHÍNH
# ==========================================
if __name__ == '__main__':
    # Khởi chạy Web Server chạy ngầm
    keep_alive()
    
    # Gửi thông báo khởi động lên Discord
    send_discord("🤖 **Bot Trading Donchian Breakout đã khởi động thành công trên Web Server!**")
    
    # Vòng lặp quét tín hiệu liên tục (mỗi 15 phút quét 1 lần)
    while True:
        try:
            analyze_and_trade()
        except Exception as e:
            print(f"❌ Lỗi hệ thống: {e}")
        time.sleep(900)
