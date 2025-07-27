import logging
import os
import pathlib
from dotenv import load_dotenv

from telegram import (
    Update,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
    BotCommand
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

from db_layer import (
    init_db,
    get_user,
    create_user,
    update_user_day,
    finish_user,
    reset_user,
    save_progress,
    get_progress,
    set_task_given,
    was_task_given,
)
from quests import QUESTS_NORMAL, QUESTS_HARD, TOTAL_DAYS

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

print("🔍 Текущая директория:", pathlib.Path().absolute())
load_dotenv(dotenv_path=pathlib.Path(__file__).parent / ".env")

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


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    create_user(user_id)

    user = get_user(user_id)
    is_finished = bool(user[2])
    hard_mode = bool(user[3])

    # Если игра завершена → предлагаем обычную или новую игру+
    if is_finished:
        kb = [["🎮 Новая игра (Обычный режим)"], ["🔥 Новая игра+ (Хардкор)"]]
    else:
        kb = [["🎮 Начать игру"]]

    await update.message.reply_text(
        "👋 Привет!\n\n"
        "Это квест *7 дней без денег*.\n"
        "Ты проживёшь неделю в городе, выполняя задания, которые развивают выживание, креатив и свободу.\n\n"
        "Готов начать?",
        reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True),
        parse_mode="Markdown"
    )


async def show_rules(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "📓 *Правила игры*\n\n"
        "Каждый день ты получаешь новое задание.\n"
        "Выполняешь → пишешь короткий отчёт → переходишь к следующему.\n"
        "Всего 7 дней.\n\n"
        "Перед началом запасись продуктами на неделю и минимальными бытовыми средствами.\n"
        "Можно пользоваться проездным или минимальными деньгами.\n\n"
        "Можно завершить игру в любой момент."
    )
    await update.message.reply_text(text, parse_mode="Markdown")


async def handle_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    user_id = update.effective_user.id

    if text in ["🎮 Начать игру", "🎮 Новая игра (Обычный режим)"]:
        reset_user(user_id, hard_mode=False)
        await update.message.reply_text("✅ Прогресс сброшен! Начинаем заново!", reply_markup=MAIN_KEYBOARD)

    elif text == "🔥 Новая игра+ (Хардкор)":
        reset_user(user_id, hard_mode=True)
        await update.message.reply_text("🔥 Хардкорный режим активирован! Удачи!", reply_markup=MAIN_KEYBOARD)

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
        await show_rules(update, context)

    elif text == "🌇 Завершить игру":
        finish_user(user_id)
        await update.message.reply_text(
            "🌇 Ты завершил игру. Спасибо за участие!\n\n"
            "Хочешь начать заново? Нажми /start"
        )

    else:
        if context.user_data.get("waiting_for_report"):
            await save_report(update, context)
        else:
            await update.message.reply_text("Выбери действие из меню!")


async def give_task(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = get_user(user_id)

    if not user:
        create_user(user_id)
        user = get_user(user_id)

    current_day = user[1]
    is_finished = user[2]
    hard_mode = bool(user[3])
    quests = QUESTS_HARD if hard_mode else QUESTS_NORMAL

    if is_finished:
        await update.message.reply_text("✅ Ты уже завершил квест!\nХочешь начать заново? Нажми /start")
        return

    next_day = current_day + 1
    if next_day > TOTAL_DAYS:
        finish_user(user_id)
        await update.message.reply_text(
            "🎉 Поздравляю! Ты прошёл все 7 дней!\n\n🔄 Можешь начать заново командой /start"
        )
        return

    task, goal = quests[next_day]
    await update.message.reply_text(
        f"📅 *День {next_day}/{TOTAL_DAYS}*\n\n🎯 *Задание:* {task}\n🎯 *Цель:* {goal}\n\nКогда выполнишь – нажми ✅ Задание выполнено.",
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardMarkup([["✅ Задание выполнено"]], resize_keyboard=True)
    )

    set_task_given(user_id, True)


async def save_report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = get_user(user_id)
    if not user:
        await update.message.reply_text("Сначала начни игру: /start")
        return

    current_day = user[1]
    text = update.message.text.strip()

    # сохраняем отчет за этот день
    save_progress(user_id, current_day + 1, text)
    # увеличиваем текущий день
    update_user_day(user_id, current_day + 1)
    # сбрасываем флаг
    set_task_given(user_id, False)

    context.user_data["waiting_for_report"] = False
    await update.message.reply_text(
        "✅ Отчёт сохранён! Отличная работа.\n\nВозвращаемся в меню.",
        reply_markup=MAIN_KEYBOARD
    )


async def show_progress(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = get_user(user_id)

    if not user:
        await update.message.reply_text("Ты ещё не начал игру. Нажми /start.")
        return

    current_day = user[1]
    hard_mode = bool(user[3])
    quests = QUESTS_HARD if hard_mode else QUESTS_NORMAL
    task_given = was_task_given(user_id)

    rows = get_progress(user_id)
    done_days = [day for day, _ in rows]

    progress_text = (
        f"📊 *Твой прогресс*\n\n"
        f"Режим: {'Новая игра+' if hard_mode else 'Обычный'}\n"
        f"📅 Пройдено {len(done_days)} из {TOTAL_DAYS} дней\n\n"
    )

    for d in range(1, TOTAL_DAYS + 1):
        if d in done_days:
            progress_text += f"✅ День {d} — {quests[d][0][:30]}...\n"
        elif d == current_day + 1 and task_given:
            progress_text += f"⏳ День {d} — {quests[d][0][:30]}...\n"
        else:
            progress_text += f"❌ День {d} — ещё не пройден\n"

    await update.message.reply_text(progress_text, parse_mode="Markdown")


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    logger.error("Ошибка:", exc_info=context.error)
    if isinstance(update, Update) and update.effective_message:
        await update.effective_message.reply_text("⚠️ Что-то пошло не так. Попробуй ещё раз!")


def main():
    init_db()
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    async def on_startup(app):
        await app.bot.set_my_commands([
            BotCommand("start", "Начать игру"),
            BotCommand("progress", "Посмотреть прогресс"),
            BotCommand("rules", "Правила игры")
        ])

    app.post_init = on_startup

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("progress", show_progress))
    app.add_handler(CommandHandler("rules", show_rules))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_menu))
    app.add_error_handler(error_handler)

    logger.info("🚀 Бот запущен…")
    app.run_polling()


if __name__ == "__main__":
    main()
