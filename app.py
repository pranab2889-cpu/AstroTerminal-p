from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
from datetime import datetime
import time
import pytz
import swisseph as swe

app = Flask(__name__)
CORS(app)

# KP New Ayanamsa
swe.set_sid_mode(swe.SIDM_KRISHNAMURTI)

PLANETS = {
    "Sun": swe.SUN, "Moon": swe.MOON, "Mars": swe.MARS, 
    "Mercury": swe.MERCURY, "Jupiter": swe.JUPITER, 
    "Venus": swe.VENUS, "Saturn": swe.SATURN, 
    "Rahu": swe.TRUE_NODE, "Ketu": swe.TRUE_NODE
}

def get_sign_lord(degree):
    lords = ["Mars", "Venus", "Mercury", "Moon", "Sun", "Mercury", "Venus", "Mars", "Jupiter", "Saturn", "Saturn", "Jupiter"]
    sign_idx = int(degree / 30) % 12
    return lords[sign_idx]

def get_kp_lords_with_timer(longitude, tz_str='Asia/Kolkata'):
    lords = ["Ketu", "Venus", "Sun", "Moon", "Mars", "Rahu", "Jupiter", "Saturn", "Mercury"]
    dasha_years = [7, 20, 6, 10, 7, 18, 16, 19, 17]
    nak_length = 13.333333333
    
    nak_idx = int(longitude / nak_length)
    nl = lords[nak_idx % 9]
    
    deg_in_nak = longitude % nak_length
    current_sl_idx = nak_idx % 9
    passed_deg = 0.0
    
    sl = ""
    ssl = ""
    deg_remaining_sl = 0.0
    
    for _ in range(9):
        sl_share = (dasha_years[current_sl_idx] / 120.0) * nak_length
        if passed_deg + sl_share >= deg_in_nak:
            sl = lords[current_sl_idx]
            deg_in_sl = deg_in_nak - passed_deg
            deg_remaining_sl = sl_share - deg_in_sl
            
            passed_ssl_deg = 0.0
            current_ssl_idx = current_sl_idx
            
            for __ in range(9):
                ssl_share = (dasha_years[current_ssl_idx] / 120.0) * sl_share
                if passed_ssl_deg + ssl_share >= deg_in_sl:
                    ssl = lords[current_ssl_idx]
                    break
                passed_ssl_deg += ssl_share
                current_ssl_idx = (current_ssl_idx + 1) % 9
            break
        passed_deg += sl_share
        current_sl_idx = (current_sl_idx + 1) % 9
        
    return nl, sl, ssl, deg_remaining_sl

def get_retrograde_status(planet_name, jd_utc, flags):
    if planet_name in ["Sun", "Moon"]: return "" 
    
    planet_id = swe.TRUE_NODE if planet_name in ["Rahu", "Ketu"] else PLANETS[planet_name]
    pos, _ = swe.calc_ut(jd_utc, planet_id, flags)
    
    if planet_name in ["Rahu", "Ketu"]:
        return " (D)" if pos[3] > 0 else " (R)" 
    else:
        return " (R)" if pos[3] < 0 else ""

def get_planetary_relation(base_planet, checking_planet):
    relations = {
        "Sun": {"Friends": ["Moon", "Mars", "Jupiter"], "Enemies": ["Venus", "Saturn", "Rahu", "Ketu"]},
        "Moon": {"Friends": ["Sun", "Mercury"], "Enemies": ["Rahu", "Ketu"]},
        "Mars": {"Friends": ["Sun", "Moon", "Jupiter"], "Enemies": ["Mercury", "Rahu"]},
        "Mercury": {"Friends": ["Sun", "Venus", "Rahu"], "Enemies": ["Moon", "Ketu"]},
        "Jupiter": {"Friends": ["Sun", "Moon", "Mars", "Rahu"], "Enemies": ["Mercury", "Venus"]},
        "Venus": {"Friends": ["Mercury", "Saturn", "Ketu"], "Enemies": ["Sun", "Moon", "Rahu"]},
        "Saturn": {"Friends": ["Mercury", "Venus", "Rahu"], "Enemies": ["Sun", "Moon", "Mars", "Ketu"]},
        "Rahu": {"Friends": ["Jupiter", "Venus", "Saturn"], "Enemies": ["Sun", "Moon", "Mars"]},
        "Ketu": {"Friends": ["Mars", "Venus", "Saturn"], "Enemies": ["Sun", "Moon"]}
    }
    clean_base = base_planet.replace(" (R)", "").replace(" (D)", "")
    clean_check = checking_planet.replace(" (R)", "").replace(" (D)", "")
    if clean_check in relations.get(clean_base, {}).get("Friends", []): return "FRIEND", "BUY", "#00e676"
    elif clean_check in relations.get(clean_base, {}).get("Enemies", []): return "ENEMY", "SELL", "#ff1744"
    else: return "NEUTRAL", "WAIT", "#ffb300"

def get_market_location(market):
    locations = {
        'NIFTY50': {'lat': 19.0760, 'lon': 72.8777, 'loc_name': 'Mumbai (NSE)', 'tz': 'Asia/Kolkata'},
        'BANKNIFTY': {'lat': 19.0760, 'lon': 72.8777, 'loc_name': 'Mumbai (NSE)', 'tz': 'Asia/Kolkata'},
        'FINNIFTY': {'lat': 19.0760, 'lon': 72.8777, 'loc_name': 'Mumbai (NSE)', 'tz': 'Asia/Kolkata'},
        'RELIANCE': {'lat': 19.0760, 'lon': 72.8777, 'loc_name': 'Mumbai (NSE)', 'tz': 'Asia/Kolkata'},
        'HDFCBANK': {'lat': 19.0760, 'lon': 72.8777, 'loc_name': 'Mumbai (NSE)', 'tz': 'Asia/Kolkata'},
        'SBI': {'lat': 19.0760, 'lon': 72.8777, 'loc_name': 'Mumbai (NSE)', 'tz': 'Asia/Kolkata'},
        'USDINR': {'lat': 19.0760, 'lon': 72.8777, 'loc_name': 'Mumbai (NSE)', 'tz': 'Asia/Kolkata'},
        'EURINR': {'lat': 19.0760, 'lon': 72.8777, 'loc_name': 'Mumbai (NSE)', 'tz': 'Asia/Kolkata'},
        'GBPINR': {'lat': 19.0760, 'lon': 72.8777, 'loc_name': 'Mumbai (NSE)', 'tz': 'Asia/Kolkata'},
        'JPYINR': {'lat': 19.0760, 'lon': 72.8777, 'loc_name': 'Mumbai (NSE)', 'tz': 'Asia/Kolkata'},
        
        'CRUDE': {'lat': 40.7128, 'lon': -74.0060, 'loc_name': 'New York (NYMEX)', 'tz': 'America/New_York'},
        'GOLD': {'lat': 40.7128, 'lon': -74.0060, 'loc_name': 'New York (COMEX)', 'tz': 'America/New_York'},
        'NATGAS': {'lat': 40.7128, 'lon': -74.0060, 'loc_name': 'New York (NYMEX)', 'tz': 'America/New_York'},
        'SILVER': {'lat': 40.7128, 'lon': -74.0060, 'loc_name': 'New York (COMEX)', 'tz': 'America/New_York'},
        
        'EURUSD': {'lat': 51.5074, 'lon': -0.1278, 'loc_name': 'London (Forex)', 'tz': 'Europe/London'},
        'GBPUSD': {'lat': 51.5074, 'lon': -0.1278, 'loc_name': 'London (Forex)', 'tz': 'Europe/London'}
    }
    return locations.get(market, {'lat': 19.0760, 'lon': 72.8777, 'loc_name': 'Mumbai (NSE)', 'tz': 'Asia/Kolkata'})

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/api/live_kp', methods=['GET'])
def live_kp():
    try:
        market = request.args.get('market', 'BANKNIFTY')
        location = get_market_location(market)
        tz_str = location.get('tz', 'Asia/Kolkata')
        
        now_utc = datetime.utcnow()
        hour_utc = now_utc.hour + now_utc.minute / 60.0 + now_utc.second / 3600.0
        jd_utc = swe.julday(now_utc.year, now_utc.month, now_utc.day, hour_utc)
        
        swe.set_topo(location['lon'], location['lat'], 0) 
        flags = swe.FLG_SIDEREAL | swe.FLG_SPEED | swe.FLG_TOPOCTR
        
        market_time = datetime.now(pytz.timezone(tz_str))
        day_lords = ["Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn"]
        rp_day_lord = day_lords[(market_time.weekday() + 1) % 7]

        # Moon Calculation
        moon_pos, _ = swe.calc_ut(jd_utc, PLANETS["Moon"], flags)
        m_nl, m_sl, m_ssl, _ = get_kp_lords_with_timer(moon_pos[0], tz_str)
        m_rashi = get_sign_lord(moon_pos[0])
        
        m_nl += get_retrograde_status(m_nl, jd_utc, flags)
        m_sl += get_retrograde_status(m_sl, jd_utc, flags)
        m_ssl += get_retrograde_status(m_ssl, jd_utc, flags)
        m_rel_text, m_signal, m_color = get_planetary_relation(m_nl, m_sl)
        
        # Ascendant (Lagna) Calculation
        cusps, ascmc = swe.houses_ex(jd_utc, location['lat'], location['lon'], b'P', flags)
        l_nl, l_sl, l_ssl, lagna_rem = get_kp_lords_with_timer(ascmc[0], tz_str)
        l_rashi = get_sign_lord(ascmc[0])
        
        l_nl += get_retrograde_status(l_nl, jd_utc, flags)
        l_sl += get_retrograde_status(l_sl, jd_utc, flags)
        l_ssl += get_retrograde_status(l_ssl, jd_utc, flags)
        
        l_rel_text, l_signal, l_color = get_planetary_relation(l_nl, l_sl)
        l_ssl_rel_text, l_ssl_signal, l_ssl_color = get_planetary_relation(l_sl, l_ssl)

        # Timer Calculation
        time_left_secs = int(lagna_rem * 240) 
        time_left_str = f"{time_left_secs // 60:02d}m {time_left_secs % 60:02d}s"

        final_signal = "WAITING"
        if l_signal == "BUY" and m_signal == "BUY": final_signal = "SUPER BUY 🚀" if l_ssl_signal == "BUY" else "BUY ENTRY"
        elif l_signal == "SELL" and m_signal == "SELL": final_signal = "PANIC SELL 💣" if l_ssl_signal == "SELL" else "SELL ENTRY"
        elif l_signal == "BUY": final_signal = "SCALP BUY ⚡"
        elif l_signal == "SELL": final_signal = "SCALP SELL ⚡"
            
        return jsonify({
            "status": "LIVE", "market": market, 
            "location": location['loc_name'], "lat": location['lat'], "lon": location['lon'],
            "final_signal": final_signal, "timer": time_left_str,
            "rp": {
                "day": rp_day_lord, "moon_rashi": m_rashi, "moon_star": m_nl.replace(' (R)', '').replace(' (D)', ''),
                "lagna_rashi": l_rashi, "lagna_star": l_nl.replace(' (R)', '').replace(' (D)', '')
            },
            "lagna": {"nl": l_nl, "sl": l_sl, "ssl": l_ssl, "relation": f"{l_sl} is {l_rel_text} of {l_nl}", "signal": l_signal, "color": l_color, "ssl_power": f"SSL ({l_ssl}) gives {l_ssl_signal}"},
            "moon": {"nl": m_nl, "sl": m_sl, "ssl": m_ssl, "relation": f"{m_sl} is {m_rel_text} of {m_nl}", "signal": m_signal, "color": m_color}
        })
    except Exception as e:
        print(f"Error: {e}")
        return jsonify({"status": "ERROR"}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5000)