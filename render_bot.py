import asyncio
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from openai import OpenAI
import yfinance as yf, pandas as pd, numpy as np
import os, re
from datetime import datetime

TELEGRAM_TOKEN = "8614945660:AAH39OdVEZv6xF2x9kqEBtEWswpi7tVLYUI"
GROQ_KEY = "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"
CHAT_ID = 5387494738
today_full = datetime.now().strftime("%d.%m.%Y %H:%M")

MODELS = ["llama-3.3-70b-versatile","gemma2-9b-it","mixtral-8x7b-32768","qwen-2.5-32b"]
MODEL_NAMES = {"llama-3.3-70b-versatile":"Llama","gemma2-9b-it":"Gemma","mixtral-8x7b-32768":"Mixtral","qwen-2.5-32b":"Qwen"}
JUDGE = "llama-3.3-70b-versatile"

SYSTEM_PROMPT = f"Сегодня {today_full}. Ты профессиональный трейдер. Отвечай ТОЛЬКО на русском. Используй ТОЛЬКО данные из запроса. Пиши кратко: цена, тренд, уровни, рекомендация. Без примеров, без общих слов."

client = OpenAI(base_url="https://api.groq.com/openai/v1",api_key=GROQ_KEY)

def get_real_price(ticker):
    try:
        d = yf.download(ticker, period="1d", interval="1h")
        if not d.empty:
            if isinstance(d.columns, pd.MultiIndex): d.columns = d.columns.droplevel(1)
            price = float(d["Close"].iloc[-1])
            high = float(d["High"].max())
            low = float(d["Low"].min())
            return f"\n[РЕАЛЬНЫЕ ДАННЫЕ на {today_full}: {ticker} = {price:.2f}, 24h High={high:.2f}, 24h Low={low:.2f}]\n"
    except: pass
    return ""

def detect_tickers(q):
    q_upper = q.upper().strip()
    patterns = {
        r'\bBTC\b':'BTC-USD', r'\bBITCOIN\b':'BTC-USD', r'БИТКОИН':'BTC-USD',
        r'\bETH\b':'ETH-USD', r'ЭФИР':'ETH-USD',
        r'\bSOL\b':'SOL-USD', r'\bXRP\b':'XRP-USD', r'\bDOGE\b':'DOGE-USD',
        r'\bAAPL\b':'AAPL', r'\bTSLA\b':'TSLA', r'\bNVDA\b':'NVDA',
        r'\bS&P\b':'^GSPC', r'\bNASDAQ\b':'^IXIC', r'\bDOW\b':'^DJI',
        r'\bDXY\b':'DX-Y.NYB', r'ИНДЕКС.ДОЛЛАР':'DX-Y.NYB',
        r'\bGOLD\b':'GC=F', r'ЗОЛОТ':'GC=F',
        r'\bOIL\b':'CL=F', r'НЕФТ':'CL=F',
        r'\bEUR/USD\b':'EURUSD=X', r'\bGBP/USD\b':'GBPUSD=X', r'\bUSD/JPY\b':'USDJPY=X',
    }
    found = []
    for pat, ticker in patterns.items():
        if re.search(pat, q_upper): found.append(ticker)
    return list(set(found))

async def ask(model,q):
    try:
        r=client.chat.completions.create(model=model,messages=[{"role":"system","content":SYSTEM_PROMPT},{"role":"user","content":q}],temperature=0.7,max_tokens=200)
        if r.choices and r.choices[0].message.content:return r.choices[0].message.content.strip()
        return "-"
    except Exception as e:return f"ошибка: {e}"

async def debate(q):
    tickers = detect_tickers(q)
    real_data = ""
    for t in tickers: real_data += get_real_price(t)
    enriched_q = q + real_data
    ans = {}
    for m in MODELS: ans[m] = await ask(m, enriched_q)
    p = SYSTEM_PROMPT + " Собери краткий итог из ответов ниже. Только суть: цена, тренд, рекомендация.\n\n"
    for m,a in ans.items(): p += f"--- {MODEL_NAMES.get(m,m)} ---\n{a}\n\n"
    v = await ask(JUDGE, p)
    r = f"{real_data.replace('[','').replace(']','')}\n\n"
    for m,a in ans.items(): r += f"{MODEL_NAMES.get(m,m)} считает:\n{a}\n\n"
    r += f"ИТОГ:\n{v}"
    return r

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Бот готов.\nТекст — дебаты 4 агентов (Groq)")

async def msg(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q=update.message.text;await update.message.reply_text("Анализирую...")
    r=await debate(q)
    if len(r)>4000:
        for i in range(0,len(r),4000):await update.message.reply_text(r[i:i+4000])
    else:await update.message.reply_text(r)

def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start",start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND,msg))
    print("Бот запущен!")
    app.run_polling()

if __name__=="__main__":
    main()
