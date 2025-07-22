import logging
import os
from telegram import (
    Update,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
    BotCommand
)
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

from db_layer import init_db, get_user, create_user, update_user_day, finish_user, save_progress, get_progress
from quests import QUESTS, TOTAL_DAYS

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("❌ BOT_TOKEN отсутствует в .env")

# === Клавиатуры ===
MAIN_KEYBOARD = ReplyKeyboardMarkup(
    [
        ["🎯 Получить задание"],
        ["📊 Мой прогресс", "📓 Правила игры"],
        ["🌇 Завершить игру"]
    ],
    resize_keyboard=True
)

# === /start ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    create_user(user_id)

    await update.message.reply_text(
        "👋 Привет!\n\n"
        "Это квест *7 дней без денег*.\n"
        "Ты проживёшь неделю в городе, выполняя задания, которые развивают выживание, креатив и свободу.\n\n"
        "Готов начать?",
        reply_markup=ReplyKeyboardMarkup([["🎮 Начать игру"]], resize_keyboard=True),
        parse_mode="Markdown"
    )

# === Главное меню и обработка кнопок ===
async def handle_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    user_id = update.effective_user.id

    if text == "🎮 Начать игру":
        await update.message.reply_text(
            "Добро пожаловать в главное меню!",
            reply_markup=MAIN_KEYBOARD
        )

    elif text == "🎯 Получить задание":
        await give_task(update, context)

    elif text == "✅ Задание выполнено":
        await update.message.reply_text(
            "Расскажи коротко, что ты сделал:",
            reply_markup=ReplyKeyboardRemove()
        )
        context.user_data["waiting_for_report"] = True

    elif text == "📊 Мой прогресс":
        await show_progress(update, context)

    elif text == "📓 Правила игры":
        await update.message.reply_text(
            "📓 *Правила игры*\n\n"
            "Каждый день ты получаешь новое задание.\n"
            "Выполняешь → пишешь короткий отчёт → переходишь к следующему.\n"
            "Всего 7 дней.\n\n"
            "Можно завершить игру в любой момент.",
            parse_mode="Markdown"
        )

    elif text == "🌇 Завершить игру":
        finish_user(user_id)
        await update.message.reply_text(
            "🌇 Ты завершил игру. Спасибо за участие!\n\n"
            "Хочешь начать заново? Нажми /start"
        )

    else:
        # Если ждём отчёт
        if context.user_data.get("waiting_for_report"):
            await save_report(update, context)
        else:
            await update.message.reply_text("Выбери действие из меню!")

# === Выдача задания ===
async def give_task(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = get_user(user_id)

    if not user:
        create_user(user_id)
        user = get_user(user_id)

    current_day = user[1]
    is_finished = user[2]

    if is_finished:
        await update.message.reply_text(
            "✅ Ты уже завершил 7-дневный квест!\n"
            "Хочешь начать заново? Нажми /start"
        )
        return

    next_day = current_day + 1
    if next_day > TOTAL_DAYS:
        finish_user(user_id)
        await update.message.reply_text(
            "🎉 Поздравляю! Ты прошёл все 7 дней!\n\n"
            "Ты победил систему на 7 дней. Свобода возможна.\n\n"
            "🔄 Можешь начать заново командой /start или поделиться с другом!"
        )
        return

    # Выдаём новое задание
    task, goal = QUESTS[next_day]
    await update.message.reply_text(
        f"📅 *День {next_day}/{TOTAL_DAYS}*\n\n"
        f"🎯 *Задание:* {task}\n"
        f"🎯 *Цель:* {goal}\n\n"
        "Когда выполнишь – нажми ✅ Задание выполнено.",
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardMarkup([["✅ Задание выполнено"]], resize_keyboard=True)
    )

    update_user_day(user_id, next_day)

# === Сохранение отчёта ===
async def save_report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = get_user(user_id)

    if not user:
        await update.message.reply_text("Сначала начни игру: /start")
        return

    current_day = user[1]
    text = update.message.text.strip()

    save_progress(user_id, current_day, text)
    context.user_data["waiting_for_report"] = False

    await update.message.reply_text(
        "✅ Отчёт сохранён! Отличная работа.\n\n"
        "Возвращаемся в меню.",
        reply_markup=MAIN_KEYBOARD
    )

# === Прогресс ===
async def show_progress(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = get_user(user_id)

    if not user:
        await update.message.reply_text("Ты ещё не начал игру. Нажми /start.")
        return

    current_day = user[1]
    rows = get_progress(user_id)

    done_days = [day for day, _ in rows]
    total = TOTAL_DAYS

    progress_text = f"📊 *Твой прогресс*\n\n📅 День {current_day} из {total}\n\n"
    for d in range(1, total + 1):
        if d in done_days:
            progress_text += f"✅ День {d} — {QUESTS[d][0][:30]}...\n"
        elif d == current_day:
            progress_text += f"⏳ День {d} — {QUESTS[d][0][:30]}...\n"
        else:
            progress_text += f"❌ День {d} — ещё не пройден\n"

    await update.message.reply_text(progress_text, parse_mode="Markdown")

# === Глобальный обработчик ошибок ===
async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    logger.error("Ошибка:", exc_info=context.error)
    if isinstance(update, Update) and update.effective_message:
        await update.effective_message.reply_text("⚠️ Что-то пошло не так. Попробуй ещё раз!")

# === Запуск бота ===
def main():
    init_db()
    app = Application.builder().token(BOT_TOKEN).build()

    async def on_startup(app: Application):
        await app.bot.set_my_commands([
            BotCommand("start", "Начать игру"),
            BotCommand("progress", "Посмотреть прогресс"),
            BotCommand("rules", "Правила игры")
        ])

    app.post_init = on_startup

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("progress", show_progress))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_menu))
    app.add_error_handler(error_handler)

    logger.info("🚀 Бот запущен…")
    app.run_polling()

if __name__ == "__main__":
    main()
