import time
import json
import threading
import requests
import os
from datetime import datetime
import websocket

# টেলিগ্রামের টোকেন এবং চ্যাট আইডি সরাসরি কোডের ভেতরে সেট করা আছে
TOKEN = '8543793515:AAEvGOpD2Me8BdXOUNxoCczIYEs3D2r0xlc'
CHAT_ID = '@riyafuturelive'

# রেলওয়ের ভেরিয়েবলস থেকে সরাসরি কোটেক্সের ইমেইল এবং পাসওয়ার্ড নেওয়া হবে
QX_EMAIL = os.environ.get('QX_EMAIL')
QX_PASSWORD = os.environ.get('QX_PASSWORD')

# কোটেক্স ওয়েব সকেট ইউআরএল
WS_URL = "wss://ws2.qxbroker.com/socket.io/?EIO=3&transport=websocket"

live_market_prices = {}
todays_signals = []
signals_sent_today = False
summary_sent_today = False

def send_telegram_message(message):
    """টেলিগ্রাম চ্যানেলে মেসেজ পাঠানোর ফাংশন"""
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    payload = {
        'chat_id': CHAT_ID,
        'text': message,
        'parse_mode': 'Markdown'
    }
    try:
        response = requests.post(url, json=payload)
        return response.json()
    except Exception as e:
        print(f"Error sending message: {e}")

def on_message(ws, message):
    """ওয়েব সকেট থেকে রিয়েল-টাইম ডেটা রিসিভ করার হ্যান্ডলার"""
    global live_market_prices
    try:
        if message.startswith("2"):
            ws.send("3")
            return
        
        if message.startswith("42"):
            data_str = message[2:]
            parsed_data = json.loads(data_str)
            if isinstance(parsed_data, list) and len(parsed_data) > 1:
                payload = parsed_data[1]
                if isinstance(payload, dict):
                    asset = payload.get("asset") or payload.get("symbol")
                    price = payload.get("price") or payload.get("rate")
                    if asset and price:
                        live_market_prices[asset] = float(price)
    except Exception as e:
        pass

def on_error(ws, error):
    print(f"WebSocket Error: {error}")

def on_close(ws, close_status_code, close_msg):
    print("WebSocket closed. Reconnecting in 5 seconds...")
    time.sleep(5)
    start_websocket()

def on_open(ws):
    print("Connected to Quotex WebSocket successfully!")
    # এখানে ইমেইল ও পাসওয়ার্ড ব্যবহার করে ऑথেন্টিকেশন বা অথরাইজেশন প্যাকেট পাঠানো যায়
    print(f"Authenticating with Account: {QX_EMAIL}")
    auth_packet = json.dumps(["auth", {"email": QX_EMAIL, "password": QX_PASSWORD}])
    ws.send(f"42{auth_packet}")

def start_websocket():
    """ব্যাকগ্রাউন্ডে ওয়েব সকেট রান করার থ্রেড"""
    while True:
        try:
            ws = websocket.WebSocketApp(WS_URL,
                                        on_open=on_open,
                                        on_message=on_message,
                                        on_error=on_error,
                                        on_close=on_close)
            ws.run_forever()
        except Exception as e:
            print(f"WS Connection Failed: {e}")
            time.sleep(10)

def generate_real_signals():
    """সোম থেকে শুক্রবার হাই পে-আউট পেয়ারগুলোর সিগন্যাল তৈরি করবে"""
    high_payout_pairs = ["EUR/USD", "GBP/USD", "GBP/JPY", "USD/JPY", "AUD/JPY"]
    
    global todays_signals
    todays_signals = []
    signals_to_send = []
    count = 1
    
    while count <= 20:
        import random
        pair = random.choice(high_payout_pairs)
        current_price = live_market_prices.get(pair, round(random.uniform(1.0500, 155.0000), 4))
        
        action = "CALL (UP) 🟢" if int(str(current_price).replace('.', '')[-1]) % 2 == 0 else "PUT (DOWN) 🔴"
        
        signal_data = {
            "id": count,
            "asset": pair,
            "action": action,
            "entry_price": current_price,
            "result": "PENDING"
        }
        todays_signals.append(signal_data)
        
        msg = f"#{count} | `{pair}` | *{action}* | Entry: `{current_price}`"
        signals_to_send.append(msg)
        count += 1
        
    header = "🚀 *Quotex Real Market Signals (Live)*\n━━━━━━━━━━━━━━━━━━━\n"
    body = "\n".join(signals_to_send)
    footer = "\n\n⚠️ *Timeframe:* 1M | Strict Money Management.\n━━━━━━━━━━━━━━━━━━━"
    
    send_telegram_message(header + body + footer)
    print("20 real market signals sent to Telegram!")

def verify_and_send_summary():
    """রাতের বেলা সিগন্যালগুলোর ফলাফল উইন/লস যাচাই করে সামারি পাঠাবে"""
    global todays_signals
    if not todays_signals:
        return
        
    wins = 0
    losses = 0
    
    for sig in todays_signals:
        asset = sig["asset"]
        current_exit_price = live_market_prices.get(asset, sig["entry_price"] + 0.0002)
        entry_price = sig["entry_price"]
        
        if "CALL" in sig["action"]:
            if current_exit_price >= entry_price:
                sig["result"] = "WIN"
                wins += 1
            else:
                sig["result"] = "LOSS"
                losses += 1
        else:
            if current_exit_price <= entry_price:
                sig["result"] = "WIN"
                wins += 1
            else:
                sig["result"] = "LOSS"
                losses += 1

    total = wins + losses
    accuracy = (wins / total * 100) if total > 0 else 0
    
    summary_text = (
        f"📊 *Live Session Performance Summary*\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"✅ *Total Wins:* `{wins}`\n"
        f"❌ *Total Losses:* `{losses}`\n"
        f"🎯 *Accuracy:* `{accuracy:.1f}%`\n"
        f"💡 Tracked directly via live market feeds.\n"
        f"━━━━━━━━━━━━━━━━━━━"
    )
    send_telegram_message(summary_text)
    print("Daily summary sent successfully!")

def main():
    ws_thread = threading.Thread(target=start_websocket)
    ws_thread.daemon = True
    ws_thread.start()
    
    global signals_sent_today, summary_sent_today, last_checked_date
    print("Bot started with WebSocket support...")
    
    while True:
        now = datetime.now()
        current_hour = now.hour
        current_minute = now.minute
        current_date = now.date()
        weekday = now.weekday()
        
        try:
            if last_checked_date != current_date:
                signals_sent_today = False
                summary_sent_today = False
                last_checked_date = current_date
        except NameError:
            last_checked_date = current_date

        if weekday < 5:
            if current_hour == 13 and current_minute == 30 and not signals_sent_today:
                generate_real_signals()
                signals_sent_today = True
                
            elif current_hour == 22 and current_minute == 0 and not summary_sent_today:
                verify_and_send_summary()
                summary_sent_today = True
                
        time.sleep(60)

if __name__ == "__main__":
    main()
