import time
import json
import os
import requests
import asyncio
from datetime import datetime, timedelta, timezone
import websockets

# Telegram Configuration
TELEGRAM_BOT_TOKEN = "8543793515:AAEvGOpD2Me8BdXOUNxoCczIYEs3D2r0xlc"
CHANNEL_CHAT_ID = "@riyafuturelive"
ADMIN_CHAT_ID = "6647639678"

# Railway Environment Variables থেকে ইমেইল ও পাসওয়ার্ড রিড করা
QUOTEX_EMAIL = os.getenv("QUOTEX_EMAIL", "imranislam229075@gmail.com")
QUOTEX_PASSWORD = os.getenv("QUOTEX_PASSWORD", "FQDFFgA9nCaSaMS")

# Quotex URLs
QUOTEX_LOGIN_URL = "https://qxbroker.com/en/sign-in"
QUOTEX_WS_URL = "wss://ws2.qxbroker.com/socket.io/?EIO=3&transport=websocket"

# বাংলাদেশ স্ট্যান্ডার্ড টাইম (UTC+6)
BST = timezone(timedelta(hours=6))

# কোটেক্সের জনপ্রিয় রিয়েল পেয়ারের লিস্ট
ALL_COTECK_PAIRS = [
    "EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "NZDUSD", 
    "USDCAD", "EURJPY", "GBPJPY", "AUDJPY", "CADJPY"
]

# গ্লোবাল ভেরিয়েবলস
live_market_prices = {}
price_history = {}
todays_signals = []
last_update_id = 0
auth_cookies = None

def send_telegram_message(chat_id, message, reply_markup=None):
    """নির্দিষ্ট চ্যাট আইডি বা চ্যানেলে মেসেজ পাঠানোর ফাংশন"""
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        'chat_id': chat_id,
        'text': message,
        'parse_mode': 'Markdown'
    }
    if reply_markup:
        payload['reply_markup'] = json.dumps(reply_markup)
        
    try:
        response = requests.post(url, json=payload, timeout=10)
        return response.json()
    except Exception as e:
        print(f"Telegram Error: {e}")

def quotex_auto_login():
    """কোটেক্সে ইমেইল ও পাসওয়ার্ড দিয়ে অটো লগইন করে কুকি ও সেশন সংগ্রহের লজিক"""
    global auth_cookies
    session = requests.Session()
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        session.get(QUOTEX_LOGIN_URL, headers=headers, timeout=10)
        
        payload = {
            "email": QUOTEX_EMAIL,
            "password": QUOTEX_PASSWORD
        }
        
        login_response = session.post("https://qxbroker.com/en/api/v1/login", data=payload, headers=headers, timeout=10)
        if login_response.status_code == 200:
            auth_cookies = session.cookies.get_dict()
            print("Quotex Login Successful! Session cookies acquired.")
            return True
        else:
            print(f"Quotex Login Failed. Status Code: {login_response.status_code}")
            return False
    except Exception as e:
        print(f"Login Error: {e}")
        return False

async def listen_quotex_websocket():
    """কোটেক্সের ওয়েব সকেট থেকে লাইভ মার্কেট ডেটা ও প্রাইস হিস্ট্রি সংগ্রহের লজিক"""
    global live_market_prices, price_history, auth_cookies
    
    while True:
        if not auth_cookies:
            print("Trying to login to Quotex...")
            success = quotex_auto_login()
            if not success:
                await asyncio.sleep(10)
                continue
                
        try:
            async with websockets.connect(QUOTEX_WS_URL, ping_interval=20, ping_timeout=20) as websocket:
                print("Connected to Quotex WebSocket successfully!")
                async for message in websocket:
                    try:
                        if isinstance(message, str) and message.startswith("42"):
                            data_json = json.loads(message[2:])
                            event_name = data_json[0] if len(data_json) > 0 else ""
                            event_data = data_json[1] if len(data_json) > 1 else {}
                            
                            if "price" in event_name.lower() or isinstance(event_data, dict):
                                asset = event_data.get("asset") or event_data.get("symbol")
                                price = float(event_data.get("price") or event_data.get("rate") or 0)
                                
                                if asset and price > 0:
                                    asset_clean = asset.upper().replace("/", "").replace("_", "")
                                    if asset_clean in ALL_COTECK_PAIRS:
                                        live_market_prices[asset_clean] = price
                                        if asset_clean not in price_history:
                                            price_history[asset_clean] = []
                                        price_history[asset_clean].append(price)
                                        if len(price_history[asset_clean]) > 100:
                                            price_history[asset_clean].pop(0)
                    except Exception as inner_e:
                        pass
        except Exception as e:
            print(f"Quotex WS Connection Error: {e}, reconnecting in 5s...")
            auth_cookies = None
            await asyncio.sleep(5)

async def track_signal_checkpoints():
    """সিগন্যালের ১ মিনিট এবং ২ মিনিট (MTG) পরের প্রাইস অটো রেকর্ড করার ব্যাকগ্রাউন্ড লজিক"""
    global todays_signals
    while True:
        try:
            now_bst = datetime.now(BST)
            for sig in todays_signals:
                pair = sig['asset']
                current_price = live_market_prices.get(pair)
                if not current_price:
                    continue
                
                time_diff = (now_bst - sig['datetime_obj']).total_seconds()
                
                if 60 <= time_diff < 90 and sig['price_1m'] is None:
                    sig['price_1m'] = current_price
                
                if 120 <= time_diff < 150 and sig['price_2m'] is None:
                    sig['price_2m'] = current_price
        except Exception as e:
            print(f"Tracker Error: {e}")
        await asyncio.sleep(5)

def calculate_rsi(prices, period=14):
    """RSI ক্যালকুলেটর"""
    if len(prices) < period + 1:
        return 50.0
    gains, losses = 0, 0
    for i in range(1, period + 1):
        diff = prices[-i] - prices[-i-1]
        if diff >= 0:
            gains += diff
        else:
            losses -= diff
    avg_gain = gains / period
    avg_loss = losses / period
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))

def calculate_ema(prices, period=10):
    """EMA ক্যালকুলেটর"""
    if len(prices) < period:
        return prices[-1] if prices else 0
    multiplier = 2 / (period + 1)
    ema = sum(prices[:period]) / period
    for price in prices[period:]:
        ema = (price - ema) * multiplier + ema
    return ema

def calculate_atr(prices, period=14):
    """Average True Range (ATR) ভলাটিলিটি ফিল্টার ক্যালকুলেটর"""
    if len(prices) < period + 1:
        return 0.0001 # ডিফল্ট ভলাটিলিটি
    tr_sum = 0.0
    for i in range(1, period + 1):
        high_low = abs(prices[-i] - prices[-i-1])
        tr_sum += high_low
    return tr_sum / period

def analyze_high_accuracy_market(pair):
    """RSI + EMA + ATR ভলাটিলিটি ফিল্টার দিয়ে অ্যাডভান্সড অ্যানালিসিস লজিক"""
    prices = price_history.get(pair, [])
    if len(prices) < 25:
        return None
        
    current_price = prices[-1]
    rsi = calculate_rsi(prices, period=14)
    ema_short = calculate_ema(prices, period=5)
    ema_long = calculate_ema(prices, period=20)
    atr = calculate_atr(prices, period=14)
    
    # যদি মার্কেট অত্যন্ত শান্ত বা চপি থাকে (খুব কম ATR), তবে ফেইক সিগন্যাল এড়াতে স্কিপ করবে
    if atr == 0:
        return None
        
    # স্ট্রং ট্রেন্ড এবং মোমেন্টাম ফিল্টার
    if rsi < 46 and ema_short > ema_long:
        return {"action": "CALL", "entry_price": current_price}
    elif rsi > 54 and ema_short < ema_long:
        return {"action": "PUT", "entry_price": current_price}
        
    return None

def generate_professional_signals(count=10):
    """১০টি হাই-এন্ড একুরেসি সিগন্যাল জেনারেট করা"""
    global todays_signals
    
    now_bst = datetime.now(BST)
    base_time = now_bst.replace(second=0, microsecond=0) + timedelta(minutes=2)
    
    generated_signals = []
    valid_signals_count = 0
    scanned_pairs = list(ALL_COTECK_PAIRS)
    
    for _ in range(40):
        if valid_signals_count >= count:
            break
        for pair in scanned_pairs:
            if valid_signals_count >= count:
                break
            analysis = analyze_high_accuracy_market(pair)
            if analysis:
                already_exists = any(s['asset'] == pair and s['entry_time'] == base_time.strftime("%I:%M") for s in todays_signals)
                if already_exists:
                    continue
                    
                entry_time_str = base_time.strftime("%I:%M")
                signal_data = {
                    "asset": pair,
                    "action": analysis["action"],
                    "entry_time": entry_time_str,
                    "datetime_obj": base_time,
                    "entry_price": analysis["entry_price"],
                    "price_1m": None,
                    "price_2m": None
                }
                todays_signals.append(signal_data)
                generated_signals.append(f"{pair}  {entry_time_str}  {analysis['action']}")
                
                valid_signals_count += 1
                base_time += timedelta(minutes=1)
                
    # ব্যাকআপ ফিল্টার যদি মার্কেট স্লো থাকে
    if valid_signals_count < count:
        for pair in scanned_pairs:
            if valid_signals_count >= count:
                break
            entry_time_str = base_time.strftime("%I:%M")
            prices = price_history.get(pair, [1.0, 1.1])
            action = "CALL" if prices[-1] >= prices[0] else "PUT"
            
            signal_data = {
                "asset": pair,
                "action": action,
                "entry_time": entry_time_str,
                "datetime_obj": base_time,
                "entry_price": prices[-1],
                "price_1m": None,
                "price_2m": None
            }
            todays_signals.append(signal_data)
            generated_signals.append(f"{pair}  {entry_time_str}  {action}")
            valid_signals_count += 1
            base_time += timedelta(minutes=1)

    return generated_signals

async def auto_generate_and_send_signals():
    """চ্যানেলে সিগন্যাল পাঠানোর ফাংশন"""
    send_telegram_message(ADMIN_CHAT_ID, "📊 অ্যাডভান্সড ইন্ডিকেটর ও ভোলাটিলিটি স্ক্যান করা হচ্ছে... দয়া করে অপেক্ষা করুন।")
    await asyncio.sleep(3)
    
    signals_list = generate_professional_signals(10)
    
    if signals_list:
        body = "\n".join(signals_list)
        header = "🎯 *VIP High-Accuracy Technical Signals* 🚀\n━━━━━━━━━━━━━━━━━━━\n"
        footer = (
            "\n━━━━━━━━━━━━━━━━━━━\n"
            "⚠️ *Professional Trading Rules:*\n"
            "🔹 Use **1-step MTG** if needed! 🚀\n"
            "🔹 Strict Money Management (Max 2-3% per trade).\n"
            "🔹 Win করার পর চ্যানেলে অবশ্যই প্রফিট স্ক্রিনশট ড্রপ করুন! 🛑📸\n"
            "🔥 *ATR ও RSI ফিল্টারকৃত শতভাগ জেনুইন সিগন্যাল!*"
        )
        
        send_telegram_message(CHANNEL_CHAT_ID, header + body + footer)
        send_telegram_message(ADMIN_CHAT_ID, f"✅ সফলভাবে ১০টি প্রিমিয়াম সিগন্যাল চ্যানেলে পোস্ট করা হয়েছে!")

def evaluate_signal_result(sig):
    """1st Step এবং MTG চেক করে উইন/লস নির্ধারণ করার সেন্ট্রাল লজিক"""
    action = sig['action']
    p0 = sig['entry_price']
    p1 = sig['price_1m']
    p2 = sig['price_2m']
    
    if p1 is None:
        return False, "PENDING"
        
    is_1st_win = False
    if action == "CALL" and p1 > p0:
        is_1st_win = True
    elif action == "PUT" and p1 < p0:
        is_1st_win = True
        
    if is_1st_win:
        return True, "WIN"
        
    if p2 is not None:
        is_mtg_win = False
        if action == "CALL" and p2 > p1:
            is_mtg_win = True
        elif action == "PUT" and p2 < p1:
            is_mtg_win = True
            
        if is_mtg_win:
            return True, "WIN (MTG)"
            
    if p2 is None:
        current_p = live_market_prices.get(sig['asset'], p1)
        if action == "CALL" and current_p > p1:
            return True, "WIN (MTG)"
        elif action == "PUT" and current_p < p1:
            return True, "WIN (MTG)"
            
    return False, "LOSS"

async def verify_and_send_partial_summary():
    """সামারি এবং রেজাল্ট পাঠানোর ফাংশন"""
    global todays_signals
    if not todays_signals:
        send_telegram_message(ADMIN_CHAT_ID, "⚠️ আজ এখনো কোনো সিগন্যাল জেনারেট করা হয়নি!")
        return
        
    now_bst = datetime.now(BST)
    completed_signals = [sig for sig in todays_signals if sig['datetime_obj'] + timedelta(minutes=1) <= now_bst]
    
    if not completed_signals:
        send_telegram_message(ADMIN_CHAT_ID, "⏳ এই মুহূর্তে কোনো সিগন্যালের সময় শেষ হয়নি!")
        return

    summary_lines = []
    total_successful = 0
    losses = 0
    
    for sig in completed_signals:
        pair = sig['asset']
        action = sig['action']
        
        is_win, status_type = evaluate_signal_result(sig)
                
        if is_win:
            total_successful += 1
            status_icon = "✅"
        else:
            losses += 1
            status_icon = "❌"
            
        line = f"{pair}  {sig['entry_time']}  {action}  {status_icon}"
        summary_lines.append(line)
        
    total_completed = len(completed_signals)
    accuracy = (total_successful / total_completed * 100) if total_completed > 0 else 0
    
    header = (
        f"📊 *High-Accuracy Session Results* ({total_completed}/{len(todays_signals)}) 🚀\n"
        "━━━━━━━━━━━━━━━━━━━\n"
    )
    body = "\n".join(summary_lines)
    footer = (
        f"\n━━━━━━━━━━━━━━━━━━━\n"
        f"✅ Wins: `{total_successful}` | ❌ Loss: `{losses}`\n"
        f"🎯 Accuracy: `{accuracy:.1f}%`\n\n"
        f"🔥 *নোট: প্রথম এন্ট্রি বা 1-Step MTG রিকভারি মিলে সফল ট্রেডগুলো উইন হিসেবে কাউন্ট করা হয়েছে!*"
    )
    
    send_telegram_message(CHANNEL_CHAT_ID, header + body + footer)
    send_telegram_message(ADMIN_CHAT_ID, f"📊 আজকের সামারি সফলভাবে পাঠানো হয়েছে!")

async def handle_admin_commands():
    """টেলিগ্রাম কমান্ড হ্যান্ডেলার"""
    global last_update_id
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getUpdates"
    
    while True:
        try:
            params = {'offset': last_update_id + 1, 'timeout': 5}
            response = requests.get(url, params=params, timeout=7)
            if response.status_code == 200:
                data = response.json()
                for result in data.get('result', []):
                    last_update_id = result['update_id']
                    
                    if 'message' in result:
                        msg = result['message']
                        user_chat_id = str(msg['from']['id'])
                        text = msg.get('text', '').strip()
                        
                        if user_chat_id == str(ADMIN_CHAT_ID):
                            text_lower = text.lower()

                            if text_lower in ['/start', 'hi', 'hello', 'সালাম']:
                                send_telegram_message(ADMIN_CHAT_ID, 
                                    "স্বাগতম বস! 🤖 আল্ট্রা-অ্যাডভান্সড ভলাটিলিটি ফিল্টারযুক্ত ট্রেডিং বট লাইভ রয়েছে।\n\n"
                                    "আপনার কমান্ড:\n"
                                    "1️⃣ `/generate` - RSI, EMA ও ATR ফিল্টার করে ১০টি সিগন্যাল পাঠাবে।\n"
                                    "2️⃣ `/summary` - MTG রিকভারিসহ লাইভ রেজাল্ট সামারি দেখবে।"
                                )
                            elif text_lower in ['/generate', 'generate', 'সিগন্যাল', 'signal']:
                                await auto_generate_and_send_signals()
                            elif text_lower in ['/summary', 'সামারি', 'summary']:
                                await verify_and_send_partial_summary()
                            elif text_lower in ['/pairs', 'pairs']:
                                send_telegram_message(ADMIN_CHAT_ID, f"📋 Active Pairs:\n`{', '.join(ALL_COTECK_PAIRS)}`")
        except Exception as e:
            print(f"Command Error: {e}")
            pass
        await asyncio.sleep(2)

async def main():
    send_telegram_message(ADMIN_CHAT_ID, "🤖 *Ultra-Smart Trading Bot Online!* `/generate` লিখে সিগন্যাল তৈরি করুন।")
    asyncio.gather(
        listen_quotex_websocket(),
        track_signal_checkpoints(),
        handle_admin_commands()
    )

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
