import yfinance as yf
import pandas as pd
import mplfinance as mpf
import matplotlib.pyplot as plt
import numpy as np

print("Скачиваю данные Биткоина...")
btc = yf.download("BTC-USD", period="1y")
print(f"Загружено {len(btc)} строк")

# Исправляем MultiIndex если есть
if isinstance(btc.columns, pd.MultiIndex):
    btc.columns = btc.columns.droplevel(1)

# Приводим всё к float
for col in ['Open', 'High', 'Low', 'Close']:
    btc[col] = btc[col].astype(float)

# Удаляем строки с пропущенными данными
btc = btc.dropna(subset=['Open', 'High', 'Low', 'Close'])

# Рассчитываем RSI 14
delta = btc['Close'].diff()
gain = delta.clip(lower=0)
loss = -delta.clip(upper=0)
avg_gain = gain.rolling(window=14).mean()
avg_loss = loss.rolling(window=14).mean()
rs = avg_gain / avg_loss
btc['RSI'] = 100 - (100 / (1 + rs))

# Создаём фигуру с двумя подграфиками
fig = plt.figure(figsize=(14, 8))

# Верхний подграфик: японские свечи
ax1 = plt.subplot(2, 1, 1)
mpf.plot(btc, type='candle', style='charles', ax=ax1, volume=False)
ax1.set_title('Биткоин BTC-USD (1 год)', fontsize=14)
ax1.set_ylabel('Цена (USD)')

# Нижний подграфик: RSI
ax2 = plt.subplot(2, 1, 2)
ax2.plot(btc.index, btc['RSI'], color='purple', linewidth=1)
ax2.axhline(70, color='red', linestyle='--', alpha=0.5)
ax2.axhline(30, color='green', linestyle='--', alpha=0.5)
ax2.fill_between(btc.index, 70, 100, alpha=0.1, color='red')
ax2.fill_between(btc.index, 0, 30, alpha=0.1, color='green')
ax2.set_ylabel('RSI (14)')
ax2.set_ylim(0, 100)
ax2.legend(['RSI', '70', '30'])

plt.tight_layout()
plt.savefig('btc_rsi_chart.png', dpi=150)
plt.close()
print("Готово! График сохранён как btc_rsi_chart.png")
