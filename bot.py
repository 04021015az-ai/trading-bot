
import asyncio
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from openai import OpenAI
import yfinance as yf, pandas as pd, numpy as np, plotly.graph_objects as go
from plotly.subplots import make_subplots
import os, re
from datetime import datetime
from scipy.signal import argrelextrema

TELEGRAM_TOKEN = "8614945660:AAH39OdVEZv6xF2x9kqEBtEWswpi7tVLYUI"
OPENROUTER_KEY = "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"
CHAT_ID = 5387494738
TICKERS = ["BTC-USD","ETH-USD","^GSPC","DX-Y.NYB","GC=F"]
PERIOD,INTERVAL,ORDER = "30d","1h",5
today = datetime.now().strftime("%d.%m.%Y %H:%M")

MODELS = ["google/gemini-2.0-flash-001","anthropic/claude-3-haiku","deepseek/deepseek-chat","qwen/qwen-2.5-72b-instruct"]
MODEL_NAMES = {"google/gemini-2.0-flash-001":"Gemini","anthropic/claude-3-haiku":"Claude","deepseek/deepseek-chat":"DeepSeek","qwen/qwen-2.5-72b-instruct":"Qwen"}
JUDGE = "google/gemini-2.0-flash-001"

SYSTEM_PROMPT = f"Сегодня {today}. Ты — профессиональный трейдер. Отвечай ТОЛЬКО на русском. Используй ТОЛЬКО данные из запроса. Пиши кратко: цена, тренд, уровни, рекомендация. Без примеров, без общих слов."

C = {"bg":"#0C0E14","paper":"#131722","text":"#787B86","up":"#FFFFFF","down":"#484848","upf":"#FFFFFF","downf":"#484848","rsi":"#7B61FF","e20":"#F6D54E","e50":"#2196F3","grid":"#1E222D","fib":"#E0A030","vu":"rgba(255,255,255,0.2)","vd":"rgba(72,72,72,0.4)"}
client = OpenAI(base_url="https://openrouter.ai/api/v1",api_key=OPENROUTER_KEY,timeout=30)

def get_real_price(ticker):
    try:
        d = yf.download(ticker, period="1d", interval="1h")
        if not d.empty:
            if isinstance(d.columns, pd.MultiIndex): d.columns = d.columns.droplevel(1)
            price = float(d["Close"].iloc[-1])
            high = float(d["High"].max())
            low = float(d["Low"].min())
            return f"\n[РЕАЛЬНЫЕ ДАННЫЕ на {today}: {ticker} = {price:.2f}, 24h High={high:.2f}, 24h Low={low:.2f}]\n"
    except: pass
    return ""

def detect_tickers(q):
    q_upper = q.upper().strip()
    patterns = {
        r'\bBTC\b': 'BTC-USD', r'\bBITCOIN\b': 'BTC-USD', r'БИТКОИН': 'BTC-USD', r'БИТОК': 'BTC-USD',
        r'\bETH\b': 'ETH-USD', r'\bETHEREUM\b': 'ETH-USD', r'ЭФИР': 'ETH-USD', r'ЭФИРИУМ': 'ETH-USD',
        r'\bSOL\b': 'SOL-USD', r'\bSOLANA\b': 'SOL-USD', r'СОЛАН': 'SOL-USD',
        r'\bXRP\b': 'XRP-USD', r'\bDOGE\b': 'DOGE-USD', r'ДОГИ': 'DOGE-USD',
        r'\bAAPL\b': 'AAPL', r'\bTSLA\b': 'TSLA', r'\bNVDA\b': 'NVDA',
        r'\bS&P\b': '^GSPC', r'\bSPX\b': '^GSPC', r'\bSP500\b': '^GSPC',
        r'\bNASDAQ\b': '^IXIC', r'\bDOW\b': '^DJI',
        r'\bDXY\b': 'DX-Y.NYB', r'ИНДЕКС.ДОЛЛАР': 'DX-Y.NYB',
        r'\bGOLD\b': 'GC=F', r'ЗОЛОТ': 'GC=F', r'\bXAU\b': 'GC=F',
        r'\bOIL\b': 'CL=F', r'НЕФТ': 'CL=F',
        r'\bEUR/USD\b': 'EURUSD=X', r'\bGBP/USD\b': 'GBPUSD=X', r'\bUSD/JPY\b': 'USDJPY=X',
    }
    found = []
    for pat, ticker in patterns.items():
        if re.search(pat, q_upper): found.append(ticker)
    return list(set(found))

async def ask(model,q):
    try:
        r=client.chat.completions.create(model=model,messages=[{"role":"system","content":SYSTEM_PROMPT},{"role":"user","content":q}],temperature=0.7,max_tokens=200)
        if r.choices and r.choices[0].message.content:return r.choices[0].message.content.strip()
        return "—"
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
    await update.message.reply_text("Бот готов.\n/chart — графики\nТекст — дебаты 4 агентов\nПоддерживает: BTC, ETH, SOL, XRP, AAPL, TSLA, S&P, DXY, Gold, Oil, EUR/USD и др.")

async def cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args=context.args;tks=[args[0].upper()]if args else TICKERS
    await update.message.reply_text("Графики...")
    for t in tks:
        fn,cap=await chart(t) if 'chart' in dir() else (None,"функция графиков отключена")
        if fn:
            with open(fn,"rb")as f:await update.message.reply_photo(photo=f,caption=cap)
            os.remove(fn)
        else:await update.message.reply_text(f"{t}: {cap}")

async def msg(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q=update.message.text;await update.message.reply_text("Анализирую...")
    r=await debate(q)
    if len(r)>4000:
        for i in range(0,len(r),4000):await update.message.reply_text(r[i:i+4000])
    else:await update.message.reply_text(r)

def main():
    app=Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start",start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND,msg))
    print("Бот запущен! 24/7 через PythonAnywhere — спроси как.")
    app.run_polling()

if __name__=="__main__":main()
