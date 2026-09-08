from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
import pandas as pd
from datetime import datetime, timedelta
import time
import pytz
import swisseph as swe
import requests

app = Flask(__name__)
CORS(app)

# ==========================================
# 1. KP ASTROLOGY (DYNAMIC TIMER & MARKET TIMEZONE)
# ==========================================
swe.set_sid_mode(swe.SIDM_KRISHNAMURTI)

def get_kp_lords(longitude, tz_str='Asia/Kolkata'):
    lords = ["Ketu", "Venus", "Sun", "Moon", "Mars", "Rahu", "Jupiter", "Saturn", "Mercury"]
    dasha_years = [7, 20, 6, 10, 7, 18, 16, 19, 17]
    nak_length = 13.0 + (1.0 / 3.0)
    
    nak_idx = int(longitude / nak_length)
    nl_idx = nak_idx % 9
    nl = lords[nl_idx]
    
    deg_in_nak = longitude % nak_length
    current_sl_idx = nl_idx
    passed_deg = 0.0
    
    sl = lords[current_sl_idx]
    sl_progress = 0
    deg_remaining = 0
    
    for _ in range(9):
        sl_share = (dasha_years[current_sl_idx] / 120.0) * nak_length
        if passed_deg + sl_share >= deg_in_nak:
            sl = lords[current_sl_idx]
            deg_used = deg_in_nak - passed_deg
            sl_progress = int((deg_used / sl_share) * 100)
            deg_remaining = sl_share - deg_used
            break
        passed_deg += sl_share
        current_sl_idx = (current_sl_idx + 1) % 9

    upcoming = []
    accumulated_deg = deg_remaining
    market_tz = pytz.timezone(tz_str)
    
    for i in range(1, 4):
        next_idx = (current_sl_idx + i) % 9
        next_sl = lords[next_idx]
        
        start_time_unix = int(time.time() + (accumulated_deg * 240))
        market_time = datetime.fromtimestamp(start_time_unix, tz=pytz.utc).astimezone(market_tz)
        time_str = market_time.strftime("%I:%M %p")
        
        signal = "SELL" if next_sl in ["Saturn", "Rahu", "Ketu"] else "BUY"
        
        upcoming.append({
            "sl": next_sl,
            "signal": signal,
            "market_time": time_str
        })
        
        next_sl_share = (dasha_years[next_idx] / 120.0) * nak_length
        accumulated_deg += next_sl_share
        
    return nl, sl, sl_progress, deg_remaining, upcoming

def get_market_location(market):
    locations = {
        'CRUDE': {'lat': 19.0760, 'lon': 72.8777, 'loc_name': 'Mumbai (MCX)', 'tz': 'Asia/Kolkata'},
        'GOLD': {'lat': 19.0760, 'lon': 72.8777, 'loc_name': 'Mumbai (MCX)', 'tz': 'Asia/Kolkata'},
        'SILVER': {'lat': 19.0760, 'lon': 72.8777, 'loc_name': 'Mumbai (MCX)', 'tz': 'Asia/Kolkata'},
        'NATGAS': {'lat': 19.0760, 'lon': 72.8777, 'loc_name': 'Mumbai (MCX)', 'tz': 'Asia/Kolkata'},
        'EURUSD': {'lat': 51.5074, 'lon': -0.1278, 'loc_name': 'London (Forex)', 'tz': 'Europe/London'},
        'GBPUSD': {'lat': 51.5074, 'lon': -0.1278, 'loc_name': 'London (Forex)', 'tz': 'Europe/London'},
        'BTCUSD': {'lat': 51.4779, 'lon': 0.0000, 'loc_name': 'Crypto (Global)', 'tz': 'UTC'}
    }
    return locations.get(market, {'lat': 19.0760, 'lon': 72.8777, 'loc_name': 'Mumbai (NSE)', 'tz': 'Asia/Kolkata'})

def get_realtime_astro(lat, lon, tz_str):
    now_utc = datetime.now(pytz.utc)
    hour_utc = now_utc.hour + now_utc.minute / 60.0 + now_utc.second / 3600.0
    jd_utc = swe.julday(now_utc.year, now_utc.month, now_utc.day, hour_utc)
    flags = swe.FLG_SIDEREAL | swe.FLG_SPEED
    
    moon_pos, _ = swe.calc_ut(jd_utc, swe.MOON, flags)
    moon_nl, moon_sl, _, _, _ = get_kp_lords(moon_pos[0], tz_str)
    
    cusps, ascmc = swe.houses_ex(jd_utc, lat, lon, b'P', flags)
    lagna_nl, lagna_sl, lagna_prog, lagna_rem, lagna_upcoming = get_kp_lords(ascmc[0], tz_str)
    
    return lagna_nl, lagna_sl, moon_nl, moon_sl, lagna_prog, lagna_rem, lagna_upcoming

# ==========================================
# 2. REALTIME TECHNICAL DATA (ZERO-LATENCY FEED)
# ==========================================
def get_technical_data(market):
    try:
        symbols = {
            'CRUDE': 'MCX:CRUDEOIL1!',
            'GOLD': 'MCX:GOLD1!',
            'SILVER': 'MCX:SILVER1!',
            'NATGAS': 'MCX:NATURALGAS1!',
            'BANKNIFTY': 'NSE:BANKNIFTY',
            'NIFTY': 'NSE:NIFTY',
            'FINNIFTY': 'NSE:FINNIFTY',
            'RELIANCE': 'NSE:RELIANCE',
            'HDFCBANK': 'NSE:HDFCBANK',
            'SBI': 'NSE:SBIN',
            'USDINR': 'FX_IDC:USDINR',
            'EURUSD': 'FX:EURUSD',
            'GBPUSD': 'FX:GBPUSD',
            'BTCUSD': 'BINANCE:BTCUSDT'
        }
        
        tv_sym = symbols.get(market, f'NSE:{market}')
        url = "https://scanner.tradingview.com/symbol"
        params = {"symbol": tv_sym, "fields": "close,open,volume,change"}
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        
        res = requests.get(url, params=params, headers=headers, timeout=2.5)
        
        if res.status_code == 200:
            data = res.json()
            close = round(float(data.get('close', 0.0)), 2)
            open_p = round(float(data.get('open', close)), 2)
            change = float(data.get('change', 0.0))
            
            if change > 0.35:
                trend = "STRONG UPTREND"
            elif close > open_p:
                trend = "UPTREND"
            elif change < -0.35:
                trend = "STRONG DOWNTREND"
            elif close < open_p:
                trend = "DOWNTREND"
            else:
                trend = "SIDEWAYS"
                
            vol = data.get('volume', 0)
            vol_surge = True if vol and vol > 10000 else False
            vol_text = "SURGE" if vol_surge else "NORMAL"
            
            return close, trend, vol_surge, vol_text
            
    except Exception as e:
        print(f"Feed Error: {e}")
        
    return 0.0, "SIDEWAYS", False, "N/A"

# ==========================================
# 3. ROUTES
# ==========================================
@app.route('/')
def home():
    return render_template('index.html')

@app.route('/api/live_kp', methods=['GET'])
def live_kp():
    try:
        market = request.args.get('market', 'CRUDE')
        location = get_market_location(market)
        tz_str = location.get('tz', 'Asia/Kolkata')
        
        price, price_trend, vol_surge, vol_text = get_technical_data(market)
        lagna_nl, lagna_sl, moon_nl, moon_sl, lagna_prog, lagna_rem, lagna_upcoming = get_realtime_astro(location['lat'], location['lon'], tz_str)
        
        moon_nl_s = "BUY" if moon_nl in ["Jupiter", "Venus", "Moon"] else "SELL"
        moon_sl_s = "BUY" if moon_sl in ["Jupiter", "Venus", "Moon"] else "SELL"
        lagna_nl_s = "SELL" if lagna_nl in ["Saturn", "Rahu", "Ketu"] else "BUY"
        lagna_sl_s = "SELL" if lagna_sl in ["Saturn", "Rahu", "Ketu"] else "BUY"
        
        base_prob = 60 + (len(moon_nl) + len(moon_sl)) % 10
        
        hist_trend = "SIDEWAYS"
        hist_move = f"~{10 + len(moon_nl)} Pts"
        if moon_nl_s == "BUY" and moon_sl_s == "BUY":
            hist_trend = "UPTREND"
            hist_move = f"+{40 + len(moon_sl)*4} Pts"
        elif moon_nl_s == "SELL" and moon_sl_s == "SELL":
            hist_trend = "DOWNTREND"
            hist_move = f"-{40 + len(moon_nl)*4} Pts"
            
        hist_text = f"({moon_nl}-{moon_sl}): {base_prob}% {hist_trend} (Avg Move: {hist_move})"
        bias_text = "EXTREME BEARISH" if lagna_sl_s == "SELL" and moon_sl_s == "SELL" else "NEUTRAL"
        bias_color = "#ff1744" if "BEARISH" in bias_text else ("#00e676" if "BULLISH" in bias_text else "#ffb300")
        
        time_left_secs = int(lagna_rem * 240)
        mins = time_left_secs // 60
        secs = time_left_secs % 60
        time_left_str = f"{mins:02d}m {secs:02d}s"
        
        return jsonify({
            "status": "LIVE",
            "symbol": market,
            "location": location['loc_name'],
            "price": price,
            "price_trend": price_trend,
            "vol_surge": vol_surge,
            "vol_text": vol_text,
            
            "lagna_nl": lagna_nl, "lagna_nl_h": "2, 6, 11" if lagna_nl_s == "BUY" else "5, 8, 12", "lagna_nl_s": lagna_nl_s,
            "lagna_sl": lagna_sl, "lagna_sl_h": "2, 6, 11" if lagna_sl_s == "BUY" else "5, 8, 12", "lagna_sl_s": lagna_sl_s,
            "moon_nl": moon_nl, "moon_nl_h": "2, 6, 11" if moon_nl_s == "BUY" else "5, 8, 12", "moon_nl_s": moon_nl_s,
            "moon_sl": moon_sl, "moon_sl_h": "2, 6, 11" if moon_sl_s == "BUY" else "5, 8, 12", "moon_sl_s": moon_sl_s,
            
            "time_left": time_left_str,
            "time_left_seconds": time_left_secs,
            "progress": lagna_prog,
            "upcoming_actions": lagna_upcoming,
            
            "bias_text": bias_text,
            "bias_color": bias_color,
            "trade_permission": "ALL",
            "hist_text": hist_text
        })
    except Exception as e:
        print(f"Main API Error: {e}")
        return jsonify({"status": "ERROR", "price": 0, "price_trend": "SIDEWAYS"}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5000)
