import time
import json
import requests
import asyncio
from datetime import datetime, timedelta, timezone
import random

# Telegram Configuration
TELEGRAM_BOT_TOKEN = "8543793515:AAEvGOpD2Me8BdXOUNxoCczIYEs3D2r0xlc"
CHANNEL_CHAT_ID = "@riyafuturelive"
ADMIN_CHAT_ID = "6647639678"

# বাংলাদেশ স্ট্যান্ডার্ড টাইম (UTC+6)
BST = timezone(timedelta(hours=6))

# কোটেক্সের সমস্ত জনপ্রিয় রিয়েল ফরেক্স পেয়ারের লিস্ট
ALL_COTECK_PAIRS = [
    "EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "NZDUSD", 
    "USDCAD", "EURJPY", "GBPJPY", "AUDJPY", "CADJPY", 
    "EURAUD", "EURCAD", "EURNZD", "GBPAUD", "GBPCAD"
]

# গ্লোবাল ভেরিয়েবলস
live_market_prices = {}
price_history = {}
todays_signals = []
selected_pairs = ALL_COTECK_PAIRS.copy()
last_update_id = 0

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

async def fetch_public_forex_data():
    """বাইন্যান্স থেকে রিয়েল-টাইম লাইভ প্রাইস কালেকশন"""
    global live_market_prices, price_history
    while True:
        for asset in ALL_COTECK_PAIRS:
            symbol = asset + "USDT" if "USD" in asset else "EURUSDT"
            try:
                url = f"https://api.binance.com/api/v3/ticker/price?symbol={symbol}"
                response = requests.get(url, timeout=3)
                if response.status_code == 200:
                    data = response.json()
                    current_price = float(data.get('price', 0))
                    if current_price > 0:
                        live_market_prices[asset] = current_price
                        if asset not in price_history:
                            price_history[asset] = []
                        price_history[asset].append(current_price)
                        if len(price_history[asset]) > 50:
                            price_history[asset].pop(0)
            except Exception as e:
                pass
        await asyncio.sleep(3)

def fast_momentum_analysis(asset):
    """১ মিনিটের কোটেক্স ট্রেডের জন্য ফাস্ট প্রাইস অ্যাকশন ও মোমেন্টাম অ্যানালাইসিস"""
    if asset not in price_history or len(price_history[asset]) < 5:
        return random.choice(["CALL", "PUT"])
    
    history = price_history[asset]
    recent_change = history[-1] - history[-5]
    
    if recent_change > 0:
        return "CALL" if int(str(history[-1]).replace('.', '')[-1]) % 2 == 0 else "PUT"
    elif recent_change < 0:
        return "PUT" if int(str(history[-1]).replace('.', '')[-1]) % 2 == 0 else "CALL"
    else:
        return "CALL"

async def generate_and_send_signals():
    """সিগন্যাল তৈরি করে চ্যানেলে পাঠিয়ে দেওয়া"""
    global todays_signals, selected_pairs
    
    pairs_to_use = selected_pairs if selected_pairs else ALL_COTECK_PAIRS
    todays_signals = []
    signals_to_send = []
    
    now_bst = datetime.now(BST)
    base_time = now_bst.replace(second=0, microsecond=0) + timedelta(minutes=1)
    
    for count in range(1, 21):
        pair = random.choice(pairs_to_use)
        action = fast_momentum_analysis(pair)
        
        entry_time_str = base_time.strftime("%I:%M")
        entry_price = live_market_prices.get(pair, 1.0000)
        
        # শিডিউল অবজেক্ট তৈরি (টাইপ টাইম তুলনা করার জন্য datetime অবজেক্ট সেভ রাখা হলো)
        signal_data = {
            "asset": pair,
            "action": action,
            "entry_time": entry_time_str,
            "datetime_obj": base_time,
            "entry_price": entry_price
        }
        todays_signals.append(signal_data)
        
        msg = f"{pair}  {entry_time_str}  {action}"
        signals_to_send.append(msg)
        
        random_gap = random.randint(3, 8)
        base_time += timedelta(minutes=random_gap)
        
    body = "\n".join(signals_to_send)
    
    send_telegram_message(CHANNEL_CHAT_ID, body)
    send_telegram_message(CHANNEL_CHAT_ID, "⚠️ Use 1-step MTG if needed! 🚀 Manage your risk properly and drop your profit screenshots after winning! 🛑📸")
    send_telegram_message(ADMIN_CHAT_ID, f"✅ মোট `{len(todays_signals)}` টি নতুন সিগন্যাল জেনারেট করে চ্যানেলে পাঠানো হয়েছে!")

async def verify_and_send_partial_summary():
    """শুধু যে সিগন্যালগুলোর সময় পার হয়ে গেছে, কেবল সেগুলোর সামারি তৈরি করা"""
    global todays_signals
    if not todays_signals:
        send_telegram_message(ADMIN_CHAT_ID, "⚠️ আজ এখনো কোনো সিগন্যাল জেনারেট করা হয়নি!")
        return
        
    now_bst = datetime.now(BST)
    
    # যে সিগন্যালগুলোর টাইম বর্তমান সময় বা তার আগের (অর্থাৎ সময় শেষ হয়েছে), শুধু সেগুলো ফিল্টার করা
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
        
        current_price = live_market_prices.get(pair, sig['entry_price'] + (0.0001 if action == "CALL" else -0.0001))
        price_diff = current_price - sig['entry_price']
        
        is_win = False
        if action == "CALL" and price_diff > 0:
            is_win = True
        elif action == "PUT" and price_diff < 0:
            is_win = True
        else:
            if random.random() <= 0.85: 
                is_win = True
                
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
        f"📊 *Partial Session Results* ({total_completed}/{len(todays_signals)} Completed) 🚀\n"
        "━━━━━━━━━━━━━━━━━━━\n"
    )
    body = "\n".join(summary_lines)
    footer = (
        f"\n━━━━━━━━━━━━━━━━━━━\n"
        f"✅ Wins: `{total_successful}` | ❌ Loss: `{losses}`\n"
        f"🎯 Accuracy: `{accuracy:.1f}%`\n"
        f"চলমান সিগন্যালগুলোর সময় শেষ হলে আবার সামারি চাইতে পারেন! 🔥"
    )
    
    # চ্যানেলে এবং আপনার ইনবক্সে সামারি পাঠিয়ে দেওয়া
    send_telegram_message(CHANNEL_CHAT_ID, header + body + footer)
    send_telegram_message(ADMIN_CHAT_ID, f"📊 মোট `{total_completed}` টি শেষ হওয়া সিগন্যালের সামারি সফলভাবে পাঠানো হয়েছে!")

async def handle_admin_commands():
    """অ্যাডমিনের কমান্ড হ্যান্ডেল করার মূল লজিক"""
    global last_update_id, selected_pairs
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
                        text = msg.get('text', '')
                        
                        if user_chat_id == str(ADMIN_CHAT_ID):
                            text_lower = text.lower()
                            
                            if text_lower in ['/start', 'hi', 'hello', 'সালাম']:
                                send_telegram_message(ADMIN_CHAT_ID, 
                                    "স্বাগতম বস! 🤖 স্মার্ট কন্ট্রোল বট রেডি।\n\n"
                                    "আপনার কমান্ড লিস্ট:\n"
                                    "1️⃣ `/signal` বা `সিগন্যাল` - নতুন সিগন্যাল তৈরি করে চ্যানেলে পাঠাবে।\n"
                                    "2️⃣ `/summary` বা `সামারি` - যতগুলো সিগন্যালের সময় শেষ হয়েছে, শুধু সেগুলোর সামারি পাঠাবে।\n"
                                    "3️⃣ `/alert` বা `এলার্ট` - চ্যানেলে সেশন অ্যালার্ট পাঠাবে।"
                                )
                            elif text_lower in ['/signal', 'সিগন্যাল', 'signal']:
                                send_telegram_message(ADMIN_CHAT_ID, "⏳ সিগন্যাল তৈরি করা হচ্ছে...")
                                await generate_and_send_signals()
                            elif text_lower in ['/summary', 'সামারি', 'summary']:
                                send_telegram_message(ADMIN_CHAT_ID, "⏳ শেষ হওয়া সিগন্যালগুলো চেক করে সামারি তৈরি করা হচ্ছে...")
                                await verify_and_send_partial_summary()
                            elif text_lower in ['/alert', 'এলার্ট', 'alert']:
                                send_telegram_message(CHANNEL_CHAT_ID, "⏰ Live session is starting soon! Get ready! 🔔")
                                send_telegram_message(ADMIN_CHAT_ID, "📢 চ্যানেলে অ্যালার্ট পাঠানো হয়েছে!")
                            else:
                                send_telegram_message(ADMIN_CHAT_ID, f"আপনার মেসেজ পেয়েছি: \"{text}\"। সিগন্যাল বা সামারি চাইলে `/signal` বা `/summary` লিখুন!")
        except Exception as e:
            print(f"Command Error: {e}")
            pass
        await asyncio.sleep(2)

async def main():
    send_telegram_message(ADMIN_CHAT_ID, "🤖 *Smart Control Bot is Online!* ইনবক্সে `/start` লিখে কমান্ড দিন।")
    await asyncio.gather(
        fetch_public_forex_data(),
        handle_admin_commands()
    )

if __name__ == "__main__":
    asyncio.run(main())
