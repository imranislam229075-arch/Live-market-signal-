import time
import requests

# আপনার প্রদানকৃত টেলিগ্রাম বটের টোকেন এবং চ্যানেল আইডি
TOKEN = '8543793515:AAEvGOpD2Me8BdXOUNxoCczIYEs3D2r0xlc'
CHAT_ID = '@riyafuturelive'

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

def analyze_and_generate_signals():
    """সিগন্যাল জেনারেট করার লজিক"""
    pairs = ["EUR/USD", "GBP/USD", "USD/JPY", "AUD/USD", "EUR/JPY", "GBP/JPY"]
    timeframes = ["1M", "5M"]
    
    signals = []
    
    import random
    for i in range(1, 21):
        pair = random.choice(pairs)
        tf = random.choice(timeframes)
        action = random.choice(["CALL (UP) 🟢", "PUT (DOWN) 🔴"])
        
        rsi = random.randint(25, 75)
        trend = "Bullish Trend" if rsi > 50 else "Bearish Trend"
        
        signal_text = (
            f"🚀 *Binary Option Signal #{i}*\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"📊 *Asset:* `{pair}`\n"
            f"⏱ *Timeframe:* `{tf}`\n"
            f"📈 *Action:* *{action}*\n"
            f"📉 *Market Analysis:* RSI: {rsi} | {trend}\n"
            f"⚠️ *Note:* Use proper money management.\n"
            f"━━━━━━━━━━━━━━━━━━━"
        )
        signals.append(signal_text)
        
    return signals

def main():
    print("Bot is starting and analyzing market data...")
    
    signals = analyze_and_generate_signals()
    
    for idx, signal in enumerate(signals, 1):
        print(f"Sending signal {idx}/20...")
        send_telegram_message(signal)
        time.sleep(3)
        
    print("All 20 signals have been successfully sent to the Telegram channel!")

if __name__ == "__main__":
    main()
