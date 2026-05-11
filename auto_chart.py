import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import asyncio
from telegram import Bot
from datetime import datetime
import os
from scipy.signal import argrelextrema

TOKEN = "8614945660:AAH39OdVEZv6xF2x9kqEBtEWswpi7tVLYUI"
CHAT_ID = 5387494738

TICKERS = [
    "BTC-USD",      # Биткоин
    "ETH-USD",      # Эфириум
    "^GSPC",        # S&P 500
    "DX-Y.NYB",     # DXY
    "GC=F",         # Золото
]

PERIOD = "30d"
INTERVAL = "1h"
ORDER = 5

C = {
    'bg': '#0C0E14', 'paper': '#131722', 'text': '#787B86',
    'candle_up': '#FFFFFF', 'candle_down': '#484848',
    'candle_up_fill': '#FFFFFF', 'candle_down_fill': '#484848',
    'rsi': '#7B61FF', 'ema20': '#F6D54E', 'ema50': '#2196F3',
    'grid': '#1E222D', 'border': '#2A2E39', 'fib': '#E0A030',
    'volume_up': 'rgba(255,255,255,0.2)', 'volume_down': 'rgba(72,72,72,0.4)'
}

def find_swings(df, order=5):
    highs = df['High'].values
    lows = df['Low'].values
    swing_high_idx = argrelextrema(highs, np.greater, order=order)[0]
    swing_low_idx = argrelextrema(lows, np.less, order=order)[0]
    return [(df.index[i], highs[i]) for i in swing_high_idx], [(df.index[i], lows[i]) for i in swing_low_idx]

def fib_levels(p1, p2):
    diff = p2 - p1
    return {
        '0': p1, '0.236': p1 + 0.236*diff, '0.382': p1 + 0.382*diff,
        '0.5': p1 + 0.5*diff, '0.618': p1 + 0.618*diff,
        '0.786': p1 + 0.786*diff, '1': p2
    }

async def send_all():
    bot = Bot(token=TOKEN)
    
    for TICKER in TICKERS:
        try:
            print(f"\n{TICKER}...")
            df = yf.download(TICKER, period=PERIOD, interval=INTERVAL)
            if df.empty:
                print(f"  Нет данных")
                continue

            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.droplevel(1)

            for col in ['Open', 'High', 'Low', 'Close', 'Volume']:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce')

            df = df.dropna(subset=['Open', 'High', 'Low', 'Close'])
            df.index = pd.to_datetime(df.index).strftime('%Y-%m-%d %H:%M')
            
            delta = df['Close'].diff()
            gain = delta.clip(lower=0)
            loss = -delta.clip(upper=0)
            df['RSI'] = 100 - (100 / (1 + gain.rolling(14).mean() / loss.rolling(14).mean()))
            df['EMA20'] = df['Close'].ewm(span=20).mean()
            df['EMA50'] = df['Close'].ewm(span=50).mean()
            
            sh, sl = find_swings(df, ORDER)
            
            trend = "Нейтрально"
            if len(sl) >= 2 and len(sh) >= 2:
                if sl[-1][1] > sl[-2][1] and sh[-1][1] > sh[-2][1]:
                    trend = "📈 Восходящий"
                elif sl[-1][1] < sl[-2][1] and sh[-1][1] < sh[-2][1]:
                    trend = "📉 Нисходящий"
                else:
                    trend = "📊 Боковик"
            
            fib_text = ""
            if sl and sh:
                start_p = min(sl[-1], sh[-1], key=lambda x: x[0])
                end_p = max(sl[-1], sh[-1], key=lambda x: x[0])
                fibs = fib_levels(start_p[1], end_p[1])
                fib_text = f"Фибо: {start_p[1]:.2f} → {end_p[1]:.2f} | 0.5: {fibs['0.5']:.2f} | 0.618: {fibs['0.618']:.2f}"
            
            fig = make_subplots(rows=3, cols=1, shared_xaxes=True,
                                vertical_spacing=0.02, row_heights=[0.55, 0.2, 0.25])
            
            fig.add_trace(go.Candlestick(
                x=df.index, open=df['Open'], high=df['High'],
                low=df['Low'], close=df['Close'], name="",
                increasing_line_color=C['candle_up'], decreasing_line_color=C['candle_down'],
                increasing_fillcolor=C['candle_up_fill'], decreasing_fillcolor=C['candle_down_fill'],
                showlegend=False
            ), row=1, col=1)
            
            fig.add_trace(go.Scatter(x=df.index, y=df['EMA20'], line=dict(color=C['ema20'], width=1), name='EMA20'), row=1, col=1)
            fig.add_trace(go.Scatter(x=df.index, y=df['EMA50'], line=dict(color=C['ema50'], width=1), name='EMA50'), row=1, col=1)
            
            if sh:
                fig.add_trace(go.Scatter(x=[s[0] for s in sh], y=[s[1] for s in sh],
                              mode='markers', marker=dict(color='red', size=5, symbol='triangle-down'), name='Макс'), row=1, col=1)
            if sl:
                fig.add_trace(go.Scatter(x=[s[0] for s in sl], y=[s[1] for s in sl],
                              mode='markers', marker=dict(color='lime', size=5, symbol='triangle-up'), name='Мин'), row=1, col=1)
            
            if sl and sh:
                for level, price in fibs.items():
                    if level in ['0', '1', '0.5', '0.618']:
                        fig.add_hline(y=price, line_dash="dash", line_color=C['fib'], opacity=0.4, row=1, col=1)
            
            colors_vol = [C['volume_up'] if df['Close'].iloc[i] >= df['Open'].iloc[i] else C['volume_down'] for i in range(len(df))]
            fig.add_trace(go.Bar(x=df.index, y=df['Volume'], marker_color=colors_vol, showlegend=False), row=2, col=1)
            
            fig.add_trace(go.Scatter(x=df.index, y=df['RSI'], line=dict(color=C['rsi'], width=1.5), name='RSI(14)'), row=3, col=1)
            fig.add_hline(y=70, line_dash="dash", line_color='red', opacity=0.5, row=3, col=1)
            fig.add_hline(y=30, line_dash="dash", line_color='green', opacity=0.5, row=3, col=1)
            
            fig.update_layout(
                template='plotly_dark', paper_bgcolor=C['bg'], plot_bgcolor=C['paper'],
                font=dict(color=C['text'], size=10), height=900, width=1500,
                title=dict(text=f'{TICKER} · 1h · 30d | {datetime.now().strftime("%H:%M")}', font=dict(size=14, color='#D1D4DC'), x=0),
                hovermode='x unified',
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                xaxis_rangeslider_visible=False,
            )
            fig.update_xaxes(gridcolor=C['grid'], showgrid=True)
            fig.update_yaxes(gridcolor=C['grid'], showgrid=True)
            
            filename = f"{TICKER.replace('/', '_').replace('^', '')}_tv.png"
            fig.write_image(filename, scale=2)
            
            with open(filename, 'rb') as photo:
                await bot.send_photo(chat_id=CHAT_ID, photo=photo,
                                    caption=f"📊 {TICKER} · 1h\n{trend}\n{fib_text}\nRSI: {df['RSI'].iloc[-1]:.1f} | Цена: {df['Close'].iloc[-1]:.2f}")
            os.remove(filename)
            print(f"  {TICKER} отправлен!")
            
        except Exception as e:
            print(f"  Ошибка {TICKER}: {e}")
    
    print("\nГотово!")

asyncio.run(send_all())
