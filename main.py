import os
import asyncio
import ccxt.async_support as ccxt
import pandas as pd
from telegram import Bot
from telegram.constants import ParseMode

BOT_TOKEN = os.getenv('BOT_TOKEN')
CHANNEL_ID = os.getenv('CHANNEL_ID')
bot = Bot(token=BOT_TOKEN)

exchange = ccxt.binance({
    'enableRateLimit': True,
    'options': {'defaultType': 'future'}
})

async def get_symbols():
    await exchange.load_markets()
    return [symbol for symbol in exchange.symbols if symbol.endswith('USDT') and exchange.markets[symbol]['active']]

async def check_signal(symbol):
    try:
        ohlcv = await exchange.fetch_ohlcv(symbol, '5m', limit=50)
        df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['ema9'] = df['close'].ewm(span=9).mean()
        df['ema21'] = df['close'].ewm(span=21).mean()
        
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        rs = gain / loss
        df['rsi'] = 100 - (100 / (1 + rs))

        last = df.iloc[-1]
        prev = df.iloc[-2]

        long_condition = (prev['ema9'] <= prev['ema21']) and (last['ema9'] > last['ema21']) and (last['rsi'] < 35)
        short_condition = (prev['ema9'] >= prev['ema21']) and (last['ema9'] < last['ema21']) and (last['rsi'] > 65)

        if long_condition or short_condition:
            direction = "LONG" if long_condition else "SHORT"
            price = last['close']
            msg = f"""
{Direction} | {symbol.replace('/USDT', 'USDT')}

Entry : {price:.4f}
TP1   : {price*1.015 if direction=="LONG" else price*0.985:.4f}
TP2   : {price*1.03 if direction=="LONG" else price*0.97:.4f}
TP3   : {price*1.05 if direction=="LONG" else price*0.95:.4f}
SL    : {price*0.985 if direction=="LONG" else price*1.015:.4f}

Leverage : 10-20x | 5m Chart
#Futures #{symbol.split('/')[0]}
{CHANNEL_ID}
            """.strip()
            await bot.send_message(chat_id=CHANNEL_ID, text=msg, parse_mode=ParseMode.MARKDOWN)
            print(f"{direction} signal sent for {symbol}")
    except Exception as e:
        pass

async def main():
    symbols = await get_symbols()
    print(f"Bot aktif! Scanning {len(symbols)} perpetual pairs setiap 5 menit...")
    await bot.send_message(chat_id=CHANNEL_ID, text="Bot Sinyal Futures Aktif! Menunggu sinyal pertama...")
    
    while True:
        for symbol in symbols:
            await check_signal(symbol)
        await asyncio.sleep(300)  # 5 menit

if __name__ == '__main__':
    asyncio.run(main())
