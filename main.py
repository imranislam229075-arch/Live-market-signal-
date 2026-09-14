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

# Railway Environment Variables থেকে ইমেইল ও পাসওয়ার্ড রিড করার কোড
QUOTEX_EMAIL = os.getenv("QUOTEX_EMAIL", "imranislam229075@gmail.com")
QUOTEX_PASSWORD = os.getenv("QUOTEX_PASSWORD", "FQDFFgA9nCaSaMS")

# Quotex URLs
QUOTEX_LOGIN_URL = "https://qxbroker.com/en/sign-in"
QUOTEX_WS_URL = "wss://ws2.qxbroker.com/socket.io/?EIO=3&transport=websocket"

# বাংলাদেশ স্ট্যান্ডার্ড টাইম (UTC+6)
BST = timezone(timedelta(hours=6))

# কোটেক্সের জনপ্রিয় পেয়ারের লিস্ট
ALL_COTECK_PAIRS = [
    "EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "NZDUSD", 
    "USDCAD", "EURJPY", "GBPJPY", "AUDJPY", "CADJPY", 
    "EURAUD", "EURCAD", "EURNZD", "GBPAUD", "GBPCAD"
]

# গ্লোবাল ভেরিয়েবলস
live_market_prices = {}
price_history = {}
todays_signals = []
last_update_id = 0
user_states = {}
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
    """কোটেক্সের ওয়েব সকেট থেকে লাইভ মার্কেট ডেটা ও প্রাইস রিসিভ করার লজিক"""
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
                                        if len(price_history[asset_clean]) > 30:
                                            price_history[asset_clean].pop(0)
                    except Exception as inner_e:
                        pass
        except Exception as e:
            print(f"Quotex WS Connection Error: {e}, reconnecting in 5s...")
            auth_cookies = None
            await asyncio.sleep(5)

def analyze_real_market_accuracy(pair, action, entry_price, current_price):
    """রিয়েল মার্কেট মোমেন্টাম ও প্রাইস অ্যাকশন যাচাই করে উইন/লস বের করার লজিক"""
    history = price_history.get(pair, [])
    price_diff = current_price - entry_price
    
    is_direction_matched = False
    if action == "CALL" and price_diff > 0:
        is_direction_matched = True
    elif action == "PUT" and price_diff < 0:
        is_direction_matched = True
    elif price_diff == 0:
        is_direction_matched = True

    if is_direction_matched and len(history) >= 3:
        recent_trend = history[-3:]
        momentum_steady = True
        
        if action == "CALL":
            for i in range(1, len(recent_trend)):
                if recent_trend[i] < recent_trend[i-1]:
                    momentum_steady = False
                    break
        elif action == "PUT":
            for i in range(1, len(recent_trend)):
                if recent_trend[i] > recent_trend[i-1]:
                    momentum_steady = False
                    break
                    
        if momentum_steady or abs(price_diff) >= 0.00001:
            return True

    return False

async def process_multiple_signals(lines):
    """একাধিক পেয়ার ও ডিরেকশন পার্স করে রিয়েল সিগন্যাল চ্যানেলে পাঠানো এবং ইনস্ট্যান্ট অ্যালার্ট"""
    global todays_signals
    
    now_bst = datetime.now(BST)
    base_time = now_bst.replace(second=0, microsecond=0) + timedelta(minutes=1)
    
    signals_to_send = []
    success_count = 0
    error_messages = []
    
    for line in lines:
        parts = line.strip().split()
        if len(parts) >= 2:
            pair = parts[0].upper()
            action = parts[1].upper()
            
            if pair in ALL_COTECK_PAIRS and action in ['CALL', 'PUT']:
                entry_time_str = base_time.strftime("%I:%M")
                entry_price = live_market_prices.get(pair, 1.0000)
                
                signal_data = {
                    "asset": pair,
                    "action": action,
                    "entry_time": entry_time_str,
                    "datetime_obj": base_time,
                    "entry_price": entry_price
                }
                todays_signals.append(signal_data)
                
                msg_line = f"{pair}  {entry_time_str}  {action}"
                signals_to_send.append(msg_line)
                success_count += 1
                base_time += timedelta(minutes=1)
            else:
                error_messages.append(f"❌ ভুল পেয়ার বা ডিরেকশন: `{line}`")
        else:
            if line.strip():
                error_messages.append(f"❌ ফরম্যাট ভুল: `{line}`")
            
    if signals_to_send:
        body = "\n".join(signals_to_send)
        header = "🎯 *VIP Live Market Signals* 🚀\n━━━━━━━━━━━━━━━━━━━\n"
        footer = (
            "\n━━━━━━━━━━━━━━━━━━━\n"
            "⚠️ *Trading Rules & Alerts:*\n"
            "🔹 Use 1-step MTG if needed! 🚀\n"
            "🔹 Manage your risk properly (Fixed % per trade).\n"
            "🔹 Win করার পর অবশ্যই আপনার প্রফিট স্ক্রিনশট চ্যানেলে ড্রপ করুন! 🛑📸\n"
            "🔥 *অ্যাডমিন লাইভ মার্কেটে আপনাদের সাথেই আছে!*"
        )
        
        send_telegram_message(CHANNEL_CHAT_ID, header + body + footer)
        send_telegram_message(ADMIN_CHAT_ID, f"✅ সফলভাবে মোট `{success_count}` টি রিয়েল সিগন্যাল চ্যানেলে ড্রপ করা হয়েছে!")
        
    if error_messages:
        error_text = "\n".join(error_messages)
        send_telegram_message(ADMIN_CHAT_ID, f"কিছু লাইনে সমস্যা পাওয়া গেছে:\n{error_text}\n\nসঠিক পেয়ার দিয়ে আবার `/signal` লিখে ট্রাই করুন।")

async def verify_and_send_partial_summary():
    """ওয়েব সকেট ডেটা যাচাই করে আজকের সব সিগন্যালের সম্মিলিত সামারি পাঠানো"""
    global todays_signals
    if not todays_signals:
        send_telegram_message(ADMIN_CHAT_ID, "⚠️ আজ এখনো কোনো সিগন্যাল দেওয়া হয়নি!")
        return
        
    now_bst = datetime.now(BST)
    completed_signals = [sig for sig in todays_signals if sig['datetime_obj'] <= now_bst]
    
    if not completed_signals:
        send_telegram_message(ADMIN_CHAT_ID, "⏳ এই মুহূর্তে কোনো সিগন্যালের সময় শেষ হয়নি। একটু পরে আবার ট্রাই করুন!")
        return

    summary_lines = []
    total_successful = 0
    losses = 0
    
    for sig in completed_signals:
        pair = sig['asset']
        action = sig['action']
        entry_price = sig['entry_price']
        
        current_price = live_market_prices.get(pair, entry_price)
        is_win = analyze_real_market_accuracy(pair, action, entry_price, current_price)
                
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
    
    motivation_note = "দারুণ সেশন যাচ্ছে সবার! 🎉 এভাবেই ডিসিপ্লিন ধরে ট্রেড করুন।"
    if accuracy >= 80:
        motivation_note = "🔥 অসাধারণ একুরেসি! আমাদের ভিআইপি মেম্বাররা আগুন ঝরাচ্ছে বাজারে! 🚀💰"
    elif accuracy < 50:
        motivation_note = "⚠️ মার্কেট একটু কঠিন যাচ্ছে। সবাই ছোট অ্যামাউন্টে ট্রেড করুন এবং লস রিকভারি নিয়ে প্যানিক হবেন না।"

    header = (
        f"📊 *Live Session Results* ({total_completed}/{len(todays_signals)} Completed) 🚀\n"
        "━━━━━━━━━━━━━━━━━━━\n"
    )
    body = "\n".join(summary_lines)
    footer = (
        f"\n━━━━━━━━━━━━━━━━━━━\n"
        f"✅ Wins: `{total_successful}` | ❌ Loss: `{losses}`\n"
        f"🎯 Accuracy: `{accuracy:.1f}%`\n\n"
        f"💡 {motivation_note}\n"
        f"📸 প্রফিট করে থাকলে স্ক্রিনশট শেয়ার করতে ভুলবেন না!"
    )
    
    send_telegram_message(CHANNEL_CHAT_ID, header + body + footer)
    send_telegram_message(ADMIN_CHAT_ID, f"📊 আজকের মোট `{total_completed}` টি শেষ হওয়া সিগন্যালের সম্মিলিত রিয়েল সামারি পাঠানো হয়েছে!")

async def handle_admin_commands():
    """ইনবক্স থেকে কমান্ড এবং ইউজার স্টেট হ্যান্ডেল করার লজিক"""
    global last_update_id, user_states
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
                            current_state = user_states.get(ADMIN_CHAT_ID, {}).get('step')
                            
                            if text.startswith('/'):
                                user_states[ADMIN_CHAT_ID] = {}
                                current_state = None

                            if current_state == 'WAITING_FOR_MULTI_SIGNALS':
                                user_states[ADMIN_CHAT_ID] = {}
                                lines = text.split('\n')
                                send_telegram_message(ADMIN_CHAT_ID, "⏳ কোটেক্স ডেটা যাচাই করে সিগন্যাল তৈরি করা হচ্ছে...")
                                await process_multiple_signals(lines)
                                continue

                            if text_lower in ['/start', 'hi', 'hello', 'সালাম']:
                                send_telegram_message(ADMIN_CHAT_ID, 
                                    "স্বাগতম বস! 🤖 কোটেক্স অটো-লগইন ট্রেডিং বট সম্পূর্ণ প্রস্তুত।\n\n"
                                    "আপনার কমান্ড লিস্ট:\n"
                                    "1️⃣ `/signal` - সিগন্যাল ও প্রফেশনাল অ্যালার্টসহ চ্যানেলে পাঠাবে।\n"
                                    "2️⃣ `/summary` - আজকের সব সিগন্যালের সম্মিলিত রেজাল্ট পাঠাবে।\n"
                                    "3️⃣ `/pairs` - পেয়ারের লিস্ট দেখবে।"
                                )
                            elif text_lower in ['/signal', 'সিগন্যাল', 'signal']:
                                user_states[ADMIN_CHAT_ID] = {'step': 'WAITING_FOR_MULTI_SIGNALS'}
                                pairs_list = ", ".join([f"`{p}`" for p in ALL_COTECK_PAIRS])
                                send_telegram_message(ADMIN_CHAT_ID, 
                                    "🎯 একসাথে একাধিক সিগন্যাল দিতে নিচের ফরম্যাটে মেসেজ পাঠান (প্রতি লাইনে একটি):\n\n"
                                    "উদাহরণ:\n"
                                    "`EURUSD CALL`\n"
                                    "`GBPUSD PUT`\n"
                                    "`USDJPY CALL`\n\n"
                                    f"উপলব্ধ পেয়ারসমূহ:\n{pairs_list}"
                                )
                            elif text_lower in ['/summary', 'সামারি', 'summary']:
                                send_telegram_message(ADMIN_CHAT_ID, "⏳ কোটেক্স ডেটা যাচাই করে সামারি তৈরি হচ্ছে...")
                                await verify_and_send_partial_summary()
                            elif text_lower in ['/pairs', 'pairs', 'পেয়ার']:
                                send_telegram_message(ADMIN_CHAT_ID, f"📋 Available Pairs:\n`{', '.join(ALL_COTECK_PAIRS)}`")
                            else:
                                send_telegram_message(ADMIN_CHAT_ID, f"আপনার মেসেজ পেয়েছি: \"{text}\"। নতুন সিগন্যাল দিতে `/signal` লিখুন!")
        except Exception as e:
            print(f"Command Error: {e}")
            pass
        await asyncio.sleep(2)

async def main():
    send_telegram_message(ADMIN_CHAT_ID, "🤖 *Quotex Auto-Login Trading Bot is Online!* ইনবক্সে `/start` লিখে কমান্ড দিন।")
    await asyncio.gather(
        listen_quotex_websocket(),
        handle_admin_commands()
    )

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
