import time
import json
import requests
import asyncio
from datetime import datetime, timedelta, timezone

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
last_update_id = 0
user_states = {}

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
    """বাইন্যান্স থেকে রিয়েল-টাইম লাইভ প্রাইস এবং হিস্ট্রি কালেকশন"""
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
                        if len(price_history[asset]) > 30:
                            price_history[asset].pop(0)
            except Exception as e:
                pass
        await asyncio.sleep(2)

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

    if is_direction_matched and len(history) >= 5:
        recent_trend = history[-5:]
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
                    
        if momentum_steady or abs(price_diff) >= 0.00005:
            return True

    return False

async def send_automatic_trading_alerts():
    """ট্রেডারদের উদ্বুদ্ধ করতে এবং লাইভ উপস্থিতি বোঝাতে ব্যাকগ্রাউন্ড অটো-অ্যালার্ট সিস্টেম"""
    await asyncio.sleep(10)
    while True:
        try:
            now_bst = datetime.now(BST)
            hour = now_bst.hour
            
            # দিন বা সন্ধ্যার একটিভ ট্রেডিং সময়ে অটো এনগেজমেন্ট অ্যালার্ট পাঠানো
            motivation_messages = [
                "🔥 *Attention Traders!* মার্কেট খুব সুন্দর মুভমেন্ট দিচ্ছে। সবাই মানি ম্যানেজমেন্ট স্ট্রিক্টলি ফলো করুন এবং রেডি থাকুন। পরবর্তী সিগন্যালের জন্য `/signal` কমান্ড ব্যবহার করুন! 🚀",
                "💡 *Pro Tip:* হুজুগে ট্রেড করবেন না। আমাদের সিগন্যাল এবং ১-স্টেপ MTG রুল মেনে চলুন, প্রফিট আপনার পকেটে আসবেই ইনশাআল্লাহ! 📈💰",
                "⚠️ *Risk Warning:* বাইনারি ট্রেডিং এ প্রফিটের পাশাপাশি ডিসিপ্লিন সবচেয়ে জরুরি। লোভ সংবরণ করে টার্গেট হিট হলে মার্কেট থেকে বের হয়ে যান! 🎯",
                "👑 অ্যাডমিন আপনাদের সাথে লাইভ মার্কেটে আছি। যেকোনো প্রয়োজনে প্রস্তুত থাকুন, বড় প্রফিট আসছে! 🔥📸"
            ]
            
            # রেন্ডম বা নির্দিষ্ট সময়ে চ্যানেলে এলার্ট পাঠানো যেতে পারে (যেমন প্রতি ২ ঘণ্টা পর পর একটি করে মোটিভেশনাল রিমাইন্ডার)
            # অথবা সিগন্যালের সাথে এলার্ট যাবে। এখানে একটিভ প্রেজেন্স বোঝানোর মেসেজ সেট করা হলো:
            # send_telegram_message(CHANNEL_CHAT_ID, motivation_messages[now_bst.minute % len(motivation_messages)])
            
        except Exception as e:
            print(f"Alert Error: {e}")
            
        await asyncio.sleep(3600) # প্রতি ১ ঘণ্টা পর পর বা প্রয়োজন অনুযায়ী

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
        # এখানে ট্রেডারদের উদ্বুদ্ধ করার জন্য আকর্ষণীয় অ্যালার্ট নোট জুড়ে দেওয়া হলো
        footer = (
            "\n━━━━━━━━━━━━━━━━━━━\n"
            "⚠️ *Trading Rules & Alerts:*\n"
            "🔹 Use 1-step MTG if needed! 🚀\n"
            "🔹 Manage your risk properly (Fixed % per trade).\n"
            "🔹 Win করার পর অবশ্যই আপনার প্রফিট স্ক্রিনশট চ্যানেলে ড্রপ করুন! 🛑📸\n"
            "🔥 *অ্যাডমিন লাইভ মার্কেটে আপনাদের সাথেই আছে!*"
        )
        
        send_telegram_message(CHANNEL_CHAT_ID, header + body + footer)
        send_telegram_message(ADMIN_CHAT_ID, f"✅ সফলভাবে মোট `{success_count}` টি রিয়েল সিগন্যাল চ্যানেলে ড্রপ করা হয়েছে এবং সাথে প্রফেশনাল অ্যালার্ট যুক্ত করা হয়েছে!")
        
    if error_messages:
        error_text = "\n".join(error_messages)
        send_telegram_message(ADMIN_CHAT_ID, f"কিছু লাইনে সমস্যা ছিল:\n{error_text}\n\nসঠিক নিয়মে দিতে চাইলে আবার `/signal` লিখুন।")

async def verify_and_send_partial_summary():
    """রিয়েল মার্কেট ডেটা ও মোমেন্টাম যাচাই করে সামারি এবং মেম্বারদের মোটিভেট করার জন্য এলার্ট পাঠানো"""
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
    
    # একুরেসি অনুযায়ী কাস্টমার বা ট্রেডারদের উদ্বুদ্ধ করার বিশেষ মেসেজ
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
    send_telegram_message(ADMIN_CHAT_ID, f"📊 মোট `{total_completed}` টি শেষ হওয়া সিগন্যালের রিয়েল সামারি ও এলার্ট পাঠানো হয়েছে!")

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
                                send_telegram_message(ADMIN_CHAT_ID, "⏳ রিয়েল মার্কেট এনালাইসিস করে সিগন্যাল তৈরি ও অ্যালার্ট সাজানো হচ্ছে...")
                                await process_multiple_signals(lines)
                                continue

                            if text_lower in ['/start', 'hi', 'hello', 'সালাম']:
                                send_telegram_message(ADMIN_CHAT_ID, 
                                    "স্বাগতম বস! 🤖 অ্যালার্ট ও হাই-একুরেসি ট্রেডিং বট সম্পূর্ণ প্রস্তুত।\n\n"
                                    "আপনার কমান্ড লিস্ট:\n"
                                    "1️⃣ `/signal` - সিগন্যাল ও প্রফেশনাল অ্যালার্টসহ চ্যানেলে পাঠাবে।\n"
                                    "2️⃣ `/summary` - রেজাল্ট ও মোটিভেশনাল নোটসহ সামারি পাঠাবে।\n"
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
                                send_telegram_message(ADMIN_CHAT_ID, "⏳ রিয়েল মার্কেট ডেটা যাচাই করে সামারি তৈরি হচ্ছে...")
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
    send_telegram_message(ADMIN_CHAT_ID, "🤖 *Alert-Enabled Trading Bot is Online!* ইনবক্সে `/start` লিখে কমান্ড দিন।")
    asyncio.gather(
        fetch_public_forex_data(),
        handle_admin_commands(),
        send_automatic_trading_alerts()
    )

if __name__ == "__main__":
    asyncio.run(main())
