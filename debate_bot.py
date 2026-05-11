import asyncio
from telegram import Bot, Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from openai import OpenAI
import os

# === НАСТРОЙКИ ===
TELEGRAM_TOKEN = "8614945660:AAH39OdVEZv6xF2x9kqEBtEWswpi7tVLYUI"
OPENROUTER_KEY = "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"
YOUR_CHAT_ID = 5387494738

# Модели для дебатов
MODELS = [
    "anthropic/claude-4-sonnet",
    "openai/gpt-4.1",
    "google/gemini-2.5-pro",
]

JUDGE_MODEL = "anthropic/claude-4-sonnet"

client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=OPENROUTER_KEY,
)

async def ask_model(model: str, question: str) -> str:
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": question}],
            temperature=0.7,
            max_tokens=500,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"Ошибка {model}: {e}"

async def debate(question: str) -> str:
    answers = {}
    for model in MODELS:
        print(f"  Спрашиваю {model}...")
        answers[model] = await ask_model(model, question)
    
    prompt = "Ты — судья. Вот ответы AI-моделей на вопрос:\n\n"
    for model, answer in answers.items():
        prompt += f"=== {model} ===\n{answer}\n\n"
    prompt += "Сравни ответы и дай итоговый вывод. Если есть противоречия — укажи их."
    
    print("  Судья анализирует...")
    verdict = await ask_model(JUDGE_MODEL, prompt)
    
    result = "🧠 ДЕБАТЫ AI\n\n"
    for model, answer in answers.items():
        short_name = model.split("/")[-1]
        result += f"🔹 {short_name}: {answer[:200]}...\n\n"
    result += f"📋 ВЕРДИКТ:\n{verdict}"
    
    return result

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id != YOUR_CHAT_ID:
        return
    await update.message.reply_text("Привет! Задай вопрос — и AI-агенты устроят дебаты.")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id != YOUR_CHAT_ID:
        return
    question = update.message.text
    await update.message.reply_text("Запускаю дебаты...")
    result = await debate(question)
    await update.message.reply_text(result)

async def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    print("Бот запущен. Задай вопрос в Telegram!")
    await app.run_polling()

if __name__ == "__main__":
    asyncio.run(main())
